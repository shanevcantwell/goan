# src/lora/lora_key_mapper.py
# Standalone script and utility functions for converting LoRA keys.
import logging
import os
import json
import re
from collections import OrderedDict
from safetensors.torch import load_file, save_file
import torch
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

UNIFIED_RULES = None

KEY_PREFIX_TRANSLATION_RULES = {
    "lora_unet_": "transformer.",
    # Add more prefix rules as needed
}

def _load_and_prepare_rules():
    """Dynamically loads all rules from all JSON files into a single, sorted list."""
    global UNIFIED_RULES
    if UNIFIED_RULES is not None:
        return

    all_rules = {}
    # Look for JSON files in the same directory as this script (src/lora/).
    mappings_dir = os.path.dirname(__file__)

    if not os.path.isdir(mappings_dir):
        # This case is unlikely as __file__ should always be in a directory.
        logger.error(f"Could not determine script directory. Cannot load LoRA mappings.")
        UNIFIED_RULES = []
        return

    json_files_found = [f for f in os.listdir(mappings_dir + "/mappings") if f.endswith('.json')]
    if not json_files_found:
        logger.warning(f"No LoRA mapping JSON files found in '{mappings_dir}'. No rules will be loaded.")
        UNIFIED_RULES = []
        return

    for filename in json_files_found:
        filepath = os.path.join(mappings_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                rules = data.get('rules', {})
                all_rules.update(rules)
                logger.debug(f"Loaded {len(rules)} rules from '{filename}' into unified set.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load LoRA mapping file '{filename}': {e}")

    # Sort by length of the source key, descending. This ensures more specific
    # rules (e.g., "_img_attn_proj") are applied before less specific ones.
    UNIFIED_RULES = sorted(all_rules.items(), key=lambda item: len(item[0]), reverse=True)
    logger.info(f"Loaded and unified {len(UNIFIED_RULES)} LoRA mapping rules from {len(json_files_found)} files.")

def _convert_hunyuan_keys_to_framepack(lora_sd: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    """
    Converts LoRA keys by applying a unified, sorted set of rules, making the
    process more robust and adaptable to hybrid naming conventions.
    """
    _load_and_prepare_rules()
    if not UNIFIED_RULES:
        logger.error("No LoRA mapping rules were loaded. Key conversion cannot proceed.")
        return lora_sd # Return original if no rules

    new_lora_sd = OrderedDict()
    for key, weight in lora_sd.items():
        new_key = key
        # Apply global prefix rules first
        for src, tgt in KEY_PREFIX_TRANSLATION_RULES.items():
            if key.startswith(src):
                new_key = tgt + key[len(src):]
                break  # Only apply the first matching rule

        # Apply the unified, sorted rules. Because rules are sorted by length,
        # this will apply the most specific match first.
        temp_key = new_key
        for src, tgt in UNIFIED_RULES:
            temp_key = temp_key.replace(src, tgt)
        new_key = temp_key

        # Final cleanup pass for numeric indices using regex.
        # This robustly handles path separators for numbered blocks (e.g., "blocks_0" -> "blocks.0").
        new_key = re.sub(r'_([0-9]+)', r'.\1', new_key)

        new_lora_sd[new_key] = weight

    logger.info(f"Converted {len(new_lora_sd)} keys using unified mapping strategy.")
    return new_lora_sd

def translate_and_analyze(lora_sd: Dict[str, torch.Tensor], model_sd: Dict[str, torch.Tensor], target_key: str) -> Tuple[Dict[str, torch.Tensor], Dict[str, Any]]:
    """
    Translates LoRA keys to the FramePack format and analyzes them against a model's state_dict.
    This function is intended for use by the application's LoRAManager.

    Args:
        lora_sd: The state dictionary of the LoRA.
        model_sd: The state dictionary of the target model (e.g., the transformer).
        target_key: The key of the target model (e.g., 'transformer'), used for prefixing.

    Returns:
        A tuple containing:
        - The translated LoRA state dictionary with only matching and valid keys.
        - A report dictionary with analysis details.
    """
    translated_lora_sd = _convert_hunyuan_keys_to_framepack(lora_sd)

    prefix_to_strip = f"{target_key}."
    final_sd = OrderedDict()
    report = {
        "keys_found": 0,
        "keys_not_found": [],
        "shape_mismatches": [],
        "total_lora_keys": 0
    }

    # We must process lora_down and lora_up pairs together for proper validation.
    lora_down_keys = [k for k in translated_lora_sd if ".lora_down." in k]
    report["total_lora_keys"] = len([k for k in translated_lora_sd if k.startswith(prefix_to_strip)])

    for key_down in lora_down_keys:
        # Filter out keys that don't belong to the current target model.
        if not key_down.startswith(prefix_to_strip):
            continue

        key_up = key_down.replace(".lora_down.weight", ".lora_up.weight")
        if key_up not in translated_lora_sd:
            logger.warning(f"Found LoRA down key '{key_down}' without a matching up key.")
            report["shape_mismatches"].append({"key": key_down, "reason": "Missing lora_up pair"})
            continue

        # Derive the key for the original weight tensor in the target model's state_dict.
        base_module_key = key_down.removeprefix(prefix_to_strip).replace(".lora_down.weight", "")
        target_weight_key = f"{base_module_key}.weight"

        if target_weight_key in model_sd:
            model_tensor = model_sd[target_weight_key]
            lora_down_tensor = translated_lora_sd[key_down]
            lora_up_tensor = translated_lora_sd[key_up]

            # Perform shape validation for a standard linear layer LoRA.
            # model_tensor: [out_features, in_features]
            # lora_down_tensor (down): [rank, in_features]
            # lora_up_tensor (up): [out_features, rank]
            rank, in_features = lora_down_tensor.shape
            out_features, _ = lora_up_tensor.shape

            if lora_down_tensor.shape == (rank, in_features) and lora_up_tensor.shape == (out_features, rank) and model_tensor.shape == (out_features, in_features):
                report["keys_found"] += 2  # Counting down and up
                final_sd[key_down] = lora_down_tensor
                final_sd[key_up] = lora_up_tensor
            else:
                mismatch_info = {
                    "key": base_module_key, "lora_down_shape": list(lora_down_tensor.shape),
                    "lora_up_shape": list(lora_up_tensor.shape), "model_shape": list(model_tensor.shape)
                }
                report["shape_mismatches"].append(mismatch_info)
                logger.warning(f"Shape mismatch for LoRA key '{base_module_key}': LoRA down is {lora_down_tensor.shape}, up is {lora_up_tensor.shape}, model is {model_tensor.shape}")
        else:
            report["keys_not_found"].extend([key_down, key_up])
            logger.debug(f"LoRA base key not found in model: '{base_module_key}' (derived from '{key_down}')")

    logger.info(f"LoRA analysis complete for target '{target_key}'. Matched {report['keys_found']} of {report['total_lora_keys']} relevant keys.")
    if report["keys_not_found"]: logger.warning(f"Found {len(report['keys_not_found'])} LoRA keys that do not exist in the target model.")
    if report["shape_mismatches"]: logger.warning(f"Found {len(report['shape_mismatches'])} LoRA keys with shape mismatches.")

    return final_sd, report

def main():
    """
    Main function to run the script from command line.
    Can be used for converting LoRA files or for analyzing key mappings.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Convert and analyze LoRA model keys.")
    parser.add_argument(
        '--convert',
        nargs=2,
        metavar=('INPUT_PATH', 'OUTPUT_PATH'),
        help="Convert a LoRA file. Takes input and output paths."
    )
    parser.add_argument(
        '--analyze',
        type=str,
        metavar='LORA_PATH',
        help="Analyze a LoRA file against the application's model, providing 'extractor' and 'target' key lists."
    )

    args = parser.parse_args()

    # Configure logging for standalone script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if args.analyze:
        lora_path = args.analyze
        if not os.path.exists(lora_path):
            print(f"Error: LoRA file not found at {lora_path}")
            return

        print("--- Analyzing LoRA and Model Keys ---")
        logger.info(f"Loading LoRA from: {lora_path}")

        # 1. Get the "Extractor" list (Raw LoRA keys)
        raw_lora_sd = load_file(lora_path)
        print(f"\n--- Raw Keys from '{os.path.basename(lora_path)}' (Extractor) ---")
        for key in sorted(raw_lora_sd.keys()):
            print(key)

        # 2. Get the "Target" list (Model keys)
        # This requires loading the model, which can be slow and memory-intensive.
        print("\n--- Loading Target Model (Transformer)... ---")
        from core import model_loader
        transformer = model_loader.get_transformer_model()
        model_sd = transformer.state_dict()
        print("\n--- Keys from Target Model (Target) ---")
        for key in sorted(model_sd.keys()):
            print(key)

        # 3. Show unmapped keys after applying current rules to guide manual mapping.
        print("\n--- Analysis of Unmapped Keys (after applying current rules) ---")
        _, report = translate_and_analyze(raw_lora_sd, model_sd, 'transformer')

        unmapped_keys = report.get('keys_not_found', [])
        if not unmapped_keys:
            print("Success! All keys appear to be mapped correctly with the current rules.")
        else:
            print(f"Found {len(unmapped_keys)} translated keys that are still unmapped:")
            # To help the user, we need to show what the unmapped key *was* before translation.
            # This requires a reverse mapping or more detailed report.
            # For now, let's show the translated key that failed to map.
            # This is what `keys_not_found` contains.
            for key in sorted(unmapped_keys):
                print(key)
        return

    if args.convert:
        input_path, output_path = args.convert
        if not os.path.exists(input_path):
            print(f"Error: LoRA file not found at {input_path}")
            return

        print(f"Loading LoRA from {input_path}...")
        lora_sd = load_file(input_path)
        
        print("Converting keys...")
        converted_sd = _convert_hunyuan_keys_to_framepack(lora_sd)
        
        print(f"Saving converted LoRA to {output_path}...")
        save_file(converted_sd, output_path)
        
        print("Conversion complete.")

if __name__ == "__main__":
    main()
