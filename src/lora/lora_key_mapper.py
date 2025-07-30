# src/core/lora_key_mapper.py
import logging
from collections import OrderedDict
import torch

logger = logging.getLogger(__name__)

# --- Translation Rules ---

# Generic prefixes from common LoRA training scripts to FramePack model prefixes.
KEY_PREFIX_TRANSLATION_RULES = {
    "lora_unet_": "transformer.",
    "lora_te_text_model_encoder_": "text_encoder.text_model.encoder.",
    "lora_te1_text_model_encoder_": "text_encoder.text_model.encoder.",
    "lora_te2_text_model_encoder_": "text_encoder_2.text_model.encoder.",
}

def _convert_hunyuan_keys_to_framepack(lora_sd: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """
    Converts LoRA weights trained on the original HunyuanVideo model to the
    FramePack model's format. This includes complex key renaming and splitting
    of combined weight tensors (e.g., QKV into separate Q, K, V).
    """
    logger.info("Hunyuan-format LoRA detected, attempting to convert keys...")
    new_lora_sd = OrderedDict()
    # This dictionary maps layer names found in common "wild" LoRAs (the key)
    # to the corresponding layer name in the FramePack model (the value).
    hunyuan_key_replacements = {
        "double_blocks": "transformer_blocks", "img_mod_linear": "norm1_linear",
        "img_attn_qkv": "attn_to_QKV", "img_attn_proj": "attn_to_out_0",
        "img_mlp_fc1": "ff_net_0_proj", "img_mlp_fc2": "ff_net_2",
        "txt_mod_linear": "norm1_context_linear", "txt_attn_qkv": "attn_add_QKV_proj",
        "txt_attn_proj": "attn_to_add_out", "txt_mlp_fc1": "ff_context_net_0_proj",
        "txt_mlp_fc2": "ff_context_net_2", "single_blocks": "single_transformer_blocks",
        "linear1": "attn_to_QKVM", "linear2": "proj_out", "modulation_linear": "norm_linear",
        # --- Dummy Example for adding a new rule ---
        # "name_in_lora_file": "name_in_framepack_model",
    }

    for key, weight in lora_sd.items():
        new_key = key
        # First, apply all known string replacements for Hunyuan format
        for src, tgt in hunyuan_key_replacements.items():
            if src in new_key:
                new_key = new_key.replace(src, tgt)

        # If no replacements were made, it's likely not a transformer block key
        if new_key == key:
            new_lora_sd[key] = weight
            continue

        # --- Weight Splitting Logic for Packed Layers ---
        if "QKVM" in new_key:
            # Split QKVM weights into separate Q, K, V, M tensors
            key_q, key_k, key_v, key_m = (
                new_key.replace("QKVM", "q"), new_key.replace("QKVM", "k"),
                new_key.replace("QKVM", "v"), new_key.replace("attn_to_QKVM", "proj_mlp")
            )
            is_down = "lora_down" in new_key or "lora_A" in new_key
            is_up = "lora_up" in new_key or "lora_B" in new_key

            if is_down or "alpha" in new_key:
                new_lora_sd[key_q], new_lora_sd[key_k], new_lora_sd[key_v], new_lora_sd[key_m] = weight, weight, weight, weight
            elif is_up:
                new_lora_sd[key_q] = weight[:3072]
                new_lora_sd[key_k] = weight[3072:6144]
                new_lora_sd[key_v] = weight[6144:9216]
                new_lora_sd[key_m] = weight[9216:]
            else: logger.warning(f"Unsupported QKVM module name: {key}")
        elif "QKV" in new_key:
            # Split QKV weights into separate Q, K, V tensors
            key_q, key_k, key_v = (new_key.replace("QKV", "q"), new_key.replace("QKV", "k"), new_key.replace("QKV", "v"))
            is_down = "lora_down" in new_key or "lora_A" in new_key
            is_up = "lora_up" in new_key or "lora_B" in new_key

            if is_down or "alpha" in new_key:
                new_lora_sd[key_q], new_lora_sd[key_k], new_lora_sd[key_v] = weight, weight, weight
            elif is_up:
                new_lora_sd[key_q] = weight[:3072]
                new_lora_sd[key_k] = weight[3072:6144]
                new_lora_sd[key_v] = weight[6144:]
            else: logger.warning(f"Unsupported QKV module name: {key}")
        else:
            new_lora_sd[new_key] = weight

    # Final pass to normalize lora_A/B to lora_down/up for consistency
    final_sd = OrderedDict()
    for key, weight in new_lora_sd.items():
        final_key = key.replace("lora_A", "lora_down").replace("lora_B", "lora_up")
        final_sd[final_key] = weight
    return final_sd

def _translate_generic_lora_keys(lora_sd: dict, model_keys: set) -> (dict, dict):
    """
    Translates keys for generic LoRAs (e.g., from Civitai) using prefix rules
    and underscore-to-dot notation conversion.
    """
    new_lora_sd = OrderedDict()
    report = {"mapped": [], "unmapped": [], "as_is": []}

    for lora_key, value in lora_sd.items():
        if ".alpha" in lora_key:
            new_lora_sd[lora_key] = value
            report["as_is"].append(lora_key)
            continue

        translated_key = lora_key
        # 1. Apply prefix rules (e.g., lora_unet_ -> transformer.)
        for src, tgt in KEY_PREFIX_TRANSLATION_RULES.items():
            if translated_key.startswith(src):
                translated_key = translated_key.replace(src, tgt, 1)
                break

        # 2. Convert underscore notation to dot notation for the module path
        # e.g., transformer.down_blocks_0_attentions_0 -> transformer.down_blocks.0.attentions.0
        parts = translated_key.split('.')
        lora_suffix = parts[-2:] # e.g., ['lora_down', 'weight']
        module_path = '.'.join(parts[:-2])
        module_path = module_path.replace('_', '.')
        final_key = f"{module_path}.{'.'.join(lora_suffix)}"

        # 3. Check if the corresponding weight exists in the target model
        model_equivalent_key = f"{module_path}.weight"
        if model_equivalent_key in model_keys:
            new_lora_sd[final_key] = value
            report["mapped"].append(f"{lora_key} -> {final_key}")
        else:
            new_lora_sd[lora_key] = value # Keep original if no match
            report["unmapped"].append(f"{lora_key} (tried: {model_equivalent_key})")

    return new_lora_sd, report

def translate_and_analyze(lora_sd: dict, model_sd: dict) -> (dict, dict):
    """
    Main entry point for LoRA key translation. Detects the LoRA format and
    applies the appropriate translation strategy.

    Returns a tuple of (translated_state_dict, analysis_report).
    """
    model_keys = set(model_sd.keys())

    # Heuristic: Check for keys unique to Hunyuan-trained LoRAs
    is_hunyuan_format = any("double_blocks" in k or "single_blocks" in k for k in lora_sd.keys())

    if is_hunyuan_format:
        translated_sd = _convert_hunyuan_keys_to_framepack(lora_sd)
        # After conversion, we still need to analyze which keys actually match the model
        report = {"mapped": [], "unmapped": [], "as_is": []}
        for key in translated_sd:
            if ".alpha" in key:
                report["as_is"].append(key)
                continue
            
            module_path = key.rsplit('.lora_down.weight', 1)[0] if 'lora_down.weight' in key else key.rsplit('.lora_up.weight', 1)[0]
            model_equivalent_key = f"{module_path}.weight"
            if model_equivalent_key in model_keys:
                report["mapped"].append(f"{key} (from Hunyuan format)")
            else:
                report["unmapped"].append(f"{key} (from Hunyuan format, no model match for {model_equivalent_key})")
        return translated_sd, report
    else:
        # Apply the generic translation for standard LoRAs
        logger.info("Standard LoRA format detected, applying generic key translation...")
        return _translate_generic_lora_keys(lora_sd, model_keys)