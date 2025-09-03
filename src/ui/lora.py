import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import gradio as gr
import shutil
import logging
from safetensors.torch import load_file
from core import model_loader
from lora import lora_key_mapper

from .enums import ComponentKey as K
from .shared_state import shared_state_instance

logger = logging.getLogger(__name__)

# Place the 'loras' directory in the project root, two levels up from 'src/ui/'
LORA_DIR = os.path.abspath(os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', 'loras')))
os.makedirs(LORA_DIR, exist_ok=True)

def list_loras():
    """Returns a list of LoRA filenames found in the LoRA directory."""
    if not os.path.exists(LORA_DIR):
        return []
    # Return a list with a blank entry so the user can "select" no LoRA for a slot.
    loras = [f for f in os.listdir(LORA_DIR) if f.endswith(('.safetensors', '.pt', '.bin'))]
    return [""] + sorted(loras)

LORA_TARGET_MAP = {
    "transformer": {"model_key": "transformer", "lora_prefix": "lora_unet"},
    "text_encoder": {"model_key": "text_encoder", "lora_prefix": "lora_te1"},
    "text_encoder_2": {"model_key": "text_encoder_2", "lora_prefix": "lora_te2"},
}

def _get_module(model, module_key):
    """Helper function to retrieve a module from a model using its key."""
    parent_module = model
    for part in module_key.split('.'):
        parent_module = parent_module[int(part)] if part.isdigit() else getattr(parent_module, part)
    return parent_module

class LoRAManager:
    def __init__(self):
        # Store original params as {model_target_key: {module_path: param}}
        # e.g., {"transformer": {"block.0.attn": tensor}}
        self._original_params = {} 
        self._applied_loras = set()
        logger.info("LoRAManager initialized.")

    def apply_lora(self, lora_name, weight_slider_val, target_modules):
        if not lora_name or not target_modules:
            return
        lora_path = os.path.join(LORA_DIR, lora_name)
        if not os.path.exists(lora_path):
            logger.error(f"LoRA file not found: {lora_path}")
            return

        logger.info(f"Applying LoRA '{lora_name}' with weight {weight_slider_val} to {target_modules}")
        try:
            raw_lora_tensors = load_file(lora_path, device="cpu")
        except Exception as e:
            logger.error(f"Failed to load LoRA file {lora_path}: {e}", exc_info=True)
            return

        for target_key in target_modules:
            map_info = LORA_TARGET_MAP.get(target_key)
            if not map_info: continue

            # Ensure transformer is loaded if it's a target
            if map_info["model_key"] == "transformer":
                shared_state_instance.models['transformer'] = model_loader.get_transformer_model()

            model = shared_state_instance.models.get(map_info["model_key"])
            if not model: continue
            
            # Use the new key mapper to translate and analyze the LoRA keys
            model_sd = model.state_dict()
            translated_lora_sd, report = lora_key_mapper.translate_and_analyze(raw_lora_tensors, model_sd, target_key)

            # Log the results from the analysis report for debugging and provide UI feedback
            keys_found = report.get('keys_found', 0)
            keys_not_found = report.get('keys_not_found', [])
            shape_mismatches = report.get('shape_mismatches', [])
            unmappable_count = len(keys_not_found) + len(shape_mismatches)

            logger.info(f"LoRA Mapping Report for '{target_key}': {keys_found} keys matched. {len(keys_not_found)} not found, {len(shape_mismatches)} shape mismatches.")
            if unmappable_count > 0:
                gr.Warning(f"LoRA '{lora_name}' had {unmappable_count} unmappable layers for target '{target_key}'. Check logs for details.")
                if keys_not_found: logger.warning(f"First 5 unmapped keys for '{target_key}': {keys_not_found[:5]}")
            
            if keys_found > 0:
                gr.Info(f"LoRA '{lora_name}' successfully mapped to {keys_found} layers for target '{target_key}'.")
            elif unmappable_count > 0: # Only show this if no layers were mapped at all
                gr.Warning(f"LoRA '{lora_name}' could not be mapped to any layers for target '{target_key}'. The LoRA may be incompatible.")

            # Use the translated state dict for merging
            self._merge_model_statically(model, translated_lora_sd, float(weight_slider_val), target_key)

        self._applied_loras.add(lora_name)

    def _merge_model_statically(self, model, translated_lora_tensors, multiplier, model_target_key):
        modified_keys_count = 0
        model_keys = set(model.state_dict().keys())

        prefix_to_strip = f"{model_target_key}."

        # Iterate through the translated LoRA weights and apply them
        lora_down_keys = [k for k in translated_lora_tensors.keys() if 'lora_down.weight' in k]

        for down_key in lora_down_keys:
            up_key = down_key.replace('lora_down.weight', 'lora_up.weight')
            alpha_key = down_key.replace('lora_down.weight', 'alpha')

            if up_key not in translated_lora_tensors: continue

            # The key from the mapper has a prefix (e.g., 'transformer.'), but the model
            # object is just the transformer itself. We must strip the prefix to get
            # the correct submodule path relative to the model object.
            base_key_with_prefix = down_key.rsplit('.lora_down.weight', 1)[0]

            if not base_key_with_prefix.startswith(prefix_to_strip):
                logger.debug(f"Skipping LoRA key '{down_key}' as it does not match target '{model_target_key}'.")
                continue

            # module_path becomes 'transformer_blocks.0.attn.to_q'
            module_path = base_key_with_prefix.removeprefix(prefix_to_strip)
            model_weight_key = f"{module_path}.weight"

            if model_weight_key not in model_keys:
                logger.debug(f"Skipping LoRA key (target weight '{model_weight_key}' not in model): {down_key}")
                continue

            # Get the actual layer module from the model
            try:
                target_layer = _get_module(model, module_path)
            except (AttributeError, KeyError) as e:
                logger.warning(f"Could not find module '{module_path}' in model for LoRA key '{down_key}'. Error: {e}")
                continue

            # --- Perform the merge ---
            try:
                device, dtype = target_layer.weight.device, target_layer.weight.dtype

                # Backup the original weight if not already backed up
                if model_target_key not in self._original_params: self._original_params[model_target_key] = {}
                if module_path not in self._original_params[model_target_key]:
                    self._original_params[model_target_key][module_path] = target_layer.weight.clone()

                down_w = translated_lora_tensors[down_key].to(device, dtype=dtype)
                up_w = translated_lora_tensors[up_key].to(device, dtype=dtype)

                # Calculate scale
                rank = down_w.shape[0] # Infer rank from the LoRA tensor itself
                alpha = translated_lora_tensors.get(alpha_key, torch.tensor(float(rank))).item()
                scale = alpha / rank if rank > 0 else 1.0
                delta_w = None

                if isinstance(target_layer, nn.Linear):
                    delta_w = (up_w @ down_w)
                elif isinstance(target_layer, nn.Conv2d):
                    if down_w.size()[2:4] == (1, 1): # Conv2d 1x1
                        delta_w = (up_w.squeeze(3).squeeze(2) @ down_w.squeeze(3).squeeze(2)).unsqueeze(2).unsqueeze(3)
                    else: # Conv2d 3x3 or other kernel sizes
                        delta_w = F.conv2d(down_w.permute(1, 0, 2, 3), up_w).permute(1, 0, 2, 3)
                
                if delta_w is not None:
                    merged_weight = (target_layer.weight.data.to(torch.float32) + (multiplier * scale * delta_w).to(torch.float32)).to(dtype)
                    target_layer.weight = nn.Parameter(merged_weight, requires_grad=False)
                    modified_keys_count += 1
                else:
                    logger.warning(f"Unsupported layer type for LoRA merge: {type(target_layer)} for key {module_path}")

            except Exception as e:
                logger.error(f"Failed to merge weights for module {module_path}: {e}", exc_info=True)
        
        if modified_keys_count > 0:
            logger.info(f"Successfully merged weights into {modified_keys_count} layers.")
        else:
            logger.warning("No layers were merged. Check LoRA compatibility and DEBUG logs.")

    def revert_all_loras(self):
        if not self._original_params: return
        logger.info(f"Reverting layers for LoRAs: {self._applied_loras}")
        
        reverted_count = 0
        for model_key, params_to_revert in self._original_params.items():
            model = shared_state_instance.models.get(model_key)
            if not model:
                logger.warning(f"Model '{model_key}' not found for reversion, skipping.")
                continue

            for module_path, original_param in params_to_revert.items():
                try:
                    # The module_path is the full path to the layer itself (e.g., 'transformer_blocks.0.attn.to_q').
                    # We need to get the layer module, not its parent.
                    target_layer = _get_module(model, module_path)
                    model_device = target_layer.weight.device
                    # Ensure the backed-up parameter is on the correct device before restoring.
                    param_to_restore = original_param.to(model_device)
                    # The original_param is a raw tensor, so it must be wrapped in nn.Parameter
                    # to correctly restore the weight of the layer.
                    target_layer.weight = nn.Parameter(param_to_restore, requires_grad=False)
                    reverted_count += 1
                except Exception as e:
                    logger.error(f"Failed to revert parameter for module {module_path} in model {model_key}: {e}", exc_info=True)
        
        logger.info(f"Reverted {reverted_count} total layers across {len(self._original_params)} models.")
        self._original_params.clear()
        self._applied_loras.clear()

def handle_lora_upload_and_update_ui(app_state, uploaded_file):
    if uploaded_file is None:
        return {
            K.APP_STATE: app_state,
            K.LORA_NAME_STATE: "",
            K.LORA_ROW: gr.update(visible=False),
            K.LORA_NAME: gr.update(value=""),
            K.LORA_WEIGHT: gr.update(value=1.0),
            K.LORA_TARGETS: gr.update(value=[])
        }    
    lora_name = os.path.basename(uploaded_file.name)
    persistent_path = os.path.join(LORA_DIR, lora_name)

    os.makedirs(os.path.dirname(persistent_path), exist_ok=True)
    shutil.copy(uploaded_file.name, persistent_path)

    logger.info(f"Saved LoRA file to: {persistent_path}")
    
    # Clear any previously loaded LoRA state to ensure a fresh start
    if "lora_state" in app_state and "loaded_loras" in app_state["lora_state"]:
        app_state["lora_state"]["loaded_loras"].clear()
        
    app_state.setdefault("lora_state", {}).setdefault("loaded_loras", {})[lora_name] = {"path": persistent_path}
    
    gr.Info(f"Loaded '{lora_name}'.")
    return {
        K.APP_STATE: app_state,
        K.LORA_NAME_STATE: lora_name,
        K.LORA_ROW: gr.update(visible=True),
        K.LORA_NAME: gr.update(value=lora_name),
        K.LORA_WEIGHT: gr.update(value=0.8),
        K.LORA_TARGETS: gr.update(value=["transformer"])
    }