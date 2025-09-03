# tools/lora_key_inspector.py
import os
import sys
import argparse
import logging

# Add the project root to the Python path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core import model_loader
from .lora_key_mapper import translate_and_analyze
from safetensors.torch import load_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def inspect_lora(lora_path: str):
    """
    Loads a LoRA file and the main application models, then prints a report
    on how the LoRA keys map to the model's layers.
    """
    if not os.path.exists(lora_path):
        logging.error(f"LoRA file not found: {lora_path}")
        return

    logging.info("Initializing application models... (This may take a moment)")
    # We only need the transformer for this analysis
    model_loader.initialize_models(load_aux_models=False)
    transformer = model_loader.get_transformer_model()
    model_state_dict = transformer.state_dict()
    logging.info("Models initialized.")

    logging.info(f"Loading LoRA from: {lora_path}")
    lora_state_dict = load_file(lora_path, device="cpu")

    logging.info("Analyzing and attempting to translate LoRA keys...")
    _, report = translate_and_analyze(lora_state_dict, model_state_dict)

    print("\n--- LoRA Key Mapping Report ---")
    print(f"File: {os.path.basename(lora_path)}\n")

    if report["mapped"]:
        print(f"✅ Successfully Mapped Keys ({len(report['mapped'])}):")
        for item in report["mapped"]:
            print(f"  - {item}")
    
    if report["unmapped"]:
        print(f"\n❌ Unmapped Keys ({len(report['unmapped'])}):")
        print("   (These layers exist in the LoRA but a corresponding layer was not found in the model)")
        for item in report["unmapped"]:
            print(f"  - {item}")

    if report["as_is"]:
        print(f"\nℹ️ Passthrough Keys ({len(report['as_is'])}):")
        for item in report["as_is"]:
            print(f"  - {item}")
    
    print("\n--- End of Report ---\n")
    logging.info("Inspection complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a LoRA file and its compatibility with the goan model.")
    parser.add_argument("lora_path", type=str, help="The full path to the .safetensors LoRA file.")
    args = parser.parse_args()
    inspect_lora(args.lora_path)