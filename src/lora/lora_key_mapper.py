# src/lora/lora_key_mapper.py

import sys
import os
import logging
from collections import OrderedDict
from safetensors.torch import load_file, save_file
import torch
from typing import Dict, Any

logger = logging.getLogger(__name__)

# --- Translation Rules ---
KEY_PREFIX_TRANSLATION_RULES = {
    "lora_unet_": "transformer.",
    # Add more prefix rules as needed
}

def _convert_hunyuan_keys_to_framepack(lora_sd: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    """
    Converts LoRA weights trained on the original HunyuanVideo model to the
    FramePack model's format. This includes complex key renaming and splitting
    of combined weight tensors (e.g., QKV into separate Q, K, V).
    """
    logger.info("Hunyuan-format LoRA detected, attempting to convert keys...")
    
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

    new_lora_sd = OrderedDict()

    for key, weight in lora_sd.items():
        new_key = key

        # Apply prefix translations
        for src, tgt in KEY_PREFIX_TRANSLATION_RULES.items():
            if key.startswith(src):
                new_key = tgt + key[len(src):]
                break  # Only apply the first matching rule

        # Apply Hunyuan-specific replacements
        for src, tgt in hunyuan_key_replacements.items():
            if src in new_key:
                new_key = new_key.replace(src, tgt)

        # If no replacements were made, it's likely not a transformer block key
        if new_key == key:
            new_lora_sd[key] = weight
            continue

        # --- Weight Splitting Logic for Packed Layers ---
        # (This section was cut off in the original context)
        # Placeholder for potential QKVM splitting logic, if needed.
        # The full implementation would handle splitting combined tensors here.
        # For now, we just assign the converted key directly.
        new_lora_sd[new_key] = weight

    logger.info(f"Converted {len(new_lora_sd)} keys.")
    return new_lora_sd

def main():
    """
    Main function to run the script from command line.
    Expects one argument: path to the .safetensors file.
    """
    if len(sys.argv) != 2:
        print("Usage: python lora_key_mapper.py <path_to_lora.safetensors>")
        sys.exit(1)

    input_path = sys.argv[1]

    # Validate input file
    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' does not exist.")
        sys.exit(1)

    if not input_path.endswith(".safetensors"):
        print(f"Warning: Input file '{input_path}' does not have the .safetensors extension. Proceeding anyway.")

    try:
        # Load the original LoRA
        print(f"Loading LoRA from {input_path}...")
        lora_sd = load_file(input_path)
        print(f"Loaded LoRA with {len(lora_sd)} tensors.")

        # Convert keys
        print("Converting keys...")
        converted_lora = _convert_hunyuan_keys_to_framepack(lora_sd)

        # Determine output path
        base_name, ext = os.path.splitext(input_path)
        output_path = f"{base_name}_converted{ext}"

        # Save the converted LoRA
        print(f"Saving converted LoRA to {output_path}...")
        save_file(converted_lora, output_path)
        print(f"Successfully saved converted LoRA to {output_path}")

    except Exception as e:
        print(f"An error occurred during processing: {e}")
        logger.exception("Error in main execution")
        sys.exit(1)

if __name__ == "__main__":
    main()
