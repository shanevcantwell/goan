# src/ui/settings_manager.py
# Manages UI settings, defaults, and loading/applying them from files.

import gradio as gr
import json
import os
import logging
from typing import Optional, Dict, Any, List, Tuple

from .enums import ComponentKey as K
from . import legacy_support
from . import shared_state as shared_state_module

logger = logging.getLogger(__name__)

class SettingsManager:
    """Manages UI settings, defaults, and loading/applying them from files."""

    def __init__(self):
        self.SETTINGS_FILENAME = "goan_settings.json"
        self.outputs_folder = './outputs/'

    def get_default_values_map(self) -> Dict[K, Any]:
        """
        Returns a dictionary with the default values for all UI settings.
        This is the single source of truth for default creative parameters.
        """
        return {
            K.POSITIVE_PROMPT: '',
            K.NEGATIVE_PROMPT: '',
            K.VIDEO_LENGTH_SLIDER: 10.0,
            K.SEED: -1,
            K.PREVIEW_FREQUENCY_SLIDER: 10,
            K.PREVIEW_SPECIFIED_SEGMENTS_TEXTBOX: '',
            K.FPS_SLIDER: 30,
            K.DISTILLED_CFG_START_SLIDER: 10.0,
            K.VARIABLE_CFG_SHAPE_RADIO: "Off",
            K.DISTILLED_CFG_END_SLIDER: 10.0,
            K.ROLL_OFF_START_SLIDER: 75,
            K.ROLL_OFF_FACTOR_SLIDER: 1.0,
            K.STEPS_SLIDER: 25,
            K.REAL_CFG_SLIDER: 1.0,
            K.GUIDANCE_RESCALE_SLIDER: 0.0,
            K.USE_TEACACHE_CHECKBOX: True,
            K.USE_FP32_TRANSFORMER_OUTPUT_CHECKBOX: False,
            K.GPU_MEMORY_PRESERVATION_SLIDER: 6.0,
            K.MP4_CRF_SLIDER: 18,
            K.OUTPUT_FOLDER_TEXTBOX: self.outputs_folder,
            K.LATENT_WINDOW_SIZE_SLIDER: 9,  # Framepack tuned to 30fps - experiment in alpha 0.3+

            K.SETTINGS_MENU_CHECKBOX_GROUP: None,
        }

    def _get_typed_value(self, key: K, value: Any, default_values: Dict[K, Any]) -> Any:
        """Casts a value to the correct type for a given component key."""
        try:
            if key in [K.SEED, K.LATENT_WINDOW_SIZE_SLIDER, K.STEPS_SLIDER, K.MP4_CRF_SLIDER, K.PREVIEW_FREQUENCY_SLIDER, K.ROLL_OFF_START_SLIDER, K.FPS_SLIDER]:
                return int(float(value))
            elif key in [K.VIDEO_LENGTH_SLIDER, K.REAL_CFG_SLIDER, K.DISTILLED_CFG_START_SLIDER, K.GUIDANCE_RESCALE_SLIDER, K.GPU_MEMORY_PRESERVATION_SLIDER, K.DISTILLED_CFG_END_SLIDER, K.ROLL_OFF_FACTOR_SLIDER]:
                return float(value)
            elif key in [K.USE_TEACACHE_CHECKBOX, K.USE_FP32_TRANSFORMER_OUTPUT_CHECKBOX]:
                return bool(value)
            return value # For strings and other types
        except (ValueError, TypeError):
            gr.Warning(f"Invalid value for {key} in loaded settings. Reverting to default.")
            return default_values.get(key)

    def get_settings_values_from_file(self, filepath: Optional[str]) -> Dict[K, Any]:
        """
        Loads settings from a file and returns a dictionary of raw, typed values.
        Used for application startup.
        """
        loaded_settings = self._load_and_parse_file(filepath)
        default_values = self.get_default_values_map()
        final_settings = {**default_values, **loaded_settings}
        
        typed_settings = {}
        for key, value in final_settings.items():
            typed_settings[key] = self._get_typed_value(key, value, default_values)
            
        return typed_settings

    def load_settings_from_file(self, filepath: Optional[str]) -> Dict[K, gr.update]:
        """
        Loads settings from a JSON file and returns a dictionary of Gradio updates.
        Conforms to the "Handler-Returns-Dict" pattern.
        """
        settings_values = self.get_settings_values_from_file(filepath)
        update_dict = {key: gr.update(value=value) for key, value in settings_values.items()}
        return update_dict

    def _load_and_parse_file(self, filepath: Optional[str]) -> Dict[K, Any]:
        """Helper to read and parse a JSON settings file."""
        if not filepath or not os.path.exists(filepath):
            if filepath:
                gr.Warning(f"Settings file not found at: {filepath}")
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_settings_str_keys = json.load(f)
            valid_keys = {item.value for item in K}
            loaded_settings = {K(k): v for k, v in loaded_settings_str_keys.items() if k in valid_keys}
            legacy_support.convert_legacy_params(loaded_settings)
            gr.Info(f"Loaded settings from {filepath}")
            return loaded_settings
        except Exception as e:
            gr.Warning(f"Could not load settings from {filepath}: {e}")
            return {}

    def save_settings_to_file(self, filepath: str, settings_dict: Dict[str, Any]):
        """Saves a dictionary of settings to a specified JSON file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=4)
            gr.Info(f"Settings saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving settings to {filepath}: {e}", exc_info=True)
            gr.Warning(f"Could not save settings to {filepath}")

    def save_default_settings_from_ui(self, all_ui_inputs: Tuple):
        """Filters and saves the default settings from the full UI state."""
        all_settings_map = dict(zip(shared_state_module.ALL_TASK_UI_KEYS, all_ui_inputs))
        
        # Exclude prompts and seed from the saved default settings.
        keys_to_exclude = {K.POSITIVE_PROMPT, K.NEGATIVE_PROMPT, K.SEED}
        
        settings_to_save = {
            key.value: value for key, value in all_settings_map.items()
            if key not in keys_to_exclude
        }
        
        self.save_settings_to_file(self.SETTINGS_FILENAME, settings_to_save)

    def get_initial_output_folder(self) -> str:
        """
        Attempts to load the 'output_folder_textbox' value from session or default settings files.
        """
        unload_save_filename = "goan_unload_save.json"
        files_to_check = [unload_save_filename, self.SETTINGS_FILENAME]

        for filename in files_to_check:
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    output_folder_key = K.OUTPUT_FOLDER_TEXTBOX.value
                    if output_folder_key in settings:
                        return os.path.expanduser(settings[output_folder_key])
                except (IOError, json.JSONDecodeError) as e:
                    logger.warning(f"Could not read output folder from {filename}: {e}")

        return self.outputs_folder

# Create the singleton instance that other modules will import.
settings_manager_instance = SettingsManager()