# src/ui/session_manager.py
# Handles saving the application state on close and restoring it on startup.

import os
import json
import tempfile
import logging
from PIL import Image
from typing import Optional, Tuple

import gradio as gr

from . import shared_state as shared_state_module
from .settings_manager import settings_manager_instance
from . import event_handler_helpers, event_handlers
from . import metadata as metadata_manager
from .enums import ComponentKey as K

logger = logging.getLogger(__name__)

# --- Constants ---
# These are now the single source of truth for session file names.
UNLOAD_SAVE_FILENAME = "goan_unload_save.json"
REFRESH_IMAGE_FILENAME = "goan_refresh_image.png"

# --- Session Saving (on close) ---

def save_ui_and_image_for_refresh(*args_from_ui_controls_tuple):
    """Saves UI state and the current image to temporary files for session recovery."""
    pil_image = args_from_ui_controls_tuple[0]
    all_ui_values_tuple = args_from_ui_controls_tuple[1:] # All UI values except the image
    full_params_map = dict(zip(shared_state_module.ALL_TASK_UI_KEYS, all_ui_values_tuple))
    settings_to_save = {key.value: value for key, value in full_params_map.items()}

    if pil_image and isinstance(pil_image, Image.Image):
        try:
            creative_ui_values = [full_params_map.get(key) for key in shared_state_module.CREATIVE_UI_KEYS]
            creative_params = metadata_manager.create_params_from_ui(shared_state_module.CREATIVE_UI_KEYS, creative_ui_values)
            pnginfo_obj = metadata_manager.create_pnginfo_obj(creative_params)

            refresh_image_path = os.path.join(tempfile.gettempdir(), REFRESH_IMAGE_FILENAME)
            pil_image.save(refresh_image_path, "PNG", pnginfo=pnginfo_obj)
            settings_to_save["refresh_image_path"] = refresh_image_path
            gr.Info(f"UI state saved, image written for refresh to {refresh_image_path}")
        except Exception as e:
            logger.error(f"Error saving refresh image: {e}", exc_info=True)
            gr.Warning(f"Could not save refresh image: {e}")
            if "refresh_image_path" in settings_to_save: del settings_to_save["refresh_image_path"]
    else:
        if "refresh_image_path" in settings_to_save: del settings_to_save["refresh_image_path"]

    settings_manager_instance.save_settings_to_file(UNLOAD_SAVE_FILENAME, settings_to_save)


# --- Session Loading (on startup) ---

def _find_startup_file_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Finds the settings and refresh image file paths for application startup.
    This is the definitive source for startup paths.
    """
    settings_file_path = None
    image_path_to_load = None

    if os.path.exists(UNLOAD_SAVE_FILENAME):
        settings_file_path = UNLOAD_SAVE_FILENAME
        try:
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if "refresh_image_path" in settings and os.path.exists(settings["refresh_image_path"]):
                image_path_to_load = settings["refresh_image_path"]
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read {UNLOAD_SAVE_FILENAME} to find refresh image: {e}")
    elif os.path.exists(settings_manager_instance.SETTINGS_FILENAME):
        settings_file_path = settings_manager_instance.SETTINGS_FILENAME

    if settings_file_path:
        logger.info(f"Found workspace file to load on startup: {settings_file_path}")
    else:
        logger.info("No workspace file found. Using default values.")

    return settings_file_path, image_path_to_load

def load_and_apply_workspace_on_start() -> dict:
    """
    Handles all application startup logic. It loads settings and the last image,
    then aggregates all necessary UI updates into a single dictionary, conforming
    to the "Handler-Returns-Dict" pattern. This dictionary is then applied to the
    UI components by the Gradio `load` event wiring.
    """
    settings_path, image_path = _find_startup_file_paths()

    pil_image = None
    if image_path:
        try:
            pil_image = Image.open(image_path)
            if REFRESH_IMAGE_FILENAME in os.path.basename(image_path) or tempfile.gettempdir() in os.path.abspath(image_path):
                os.remove(image_path)
        except Exception as e:
            logger.error(f"Failed to load refresh image on startup: {e}")
            pil_image = None

    # 1. Initialize the dictionary to hold all UI updates.
    all_updates = {}

    # 2. Load settings from the manager.
    settings_values_map = settings_manager_instance.get_settings_values_from_file(settings_path)
    for key, value in settings_values_map.items():
        # --- THE CORRECT MINIMAL FIX ---
        # The relaunch notification should not persist across sessions.
        # We skip loading it from the settings file to prevent a crash if the file
        # contains a corrupt value (like a list) and to ensure it's cleared on start.
        if key == K.RELAUNCH_NOTIFICATION_MD:
           continue
        # The Latent Window Size is a non-interactive "magic number" for the model.
        # It should never be loaded from a settings file, as a corrupted or stale
        # file could break generation. We always want it to use the default value
        # defined in the layout.
        if key == K.LATENT_WINDOW_SIZE_SLIDER:
           continue
        # Ensure the value is a string before passing it to gr.update for Markdown components
        if isinstance(value, list):
            logger.warning(f"Found list value for UI component '{key.value}' during startup load. Coercing to string. Original value: {value}")
            value = "".join(map(str, value))  # Convert list to string safely
        all_updates[key] = gr.update(value=value)

    # 3. Handle the image component updates.
    has_image = pil_image is not None
    all_updates[K.INPUT_IMAGE_DISPLAY] = gr.update(value=pil_image, visible=has_image)
    all_updates[K.CLEAR_IMAGE_BUTTON] = gr.update(interactive=has_image)
    all_updates[K.DOWNLOAD_IMAGE_BUTTON] = gr.update(interactive=has_image)
    all_updates[K.IMAGE_FILE_INPUT] = gr.update(visible=not has_image)

    # 4. Get button state updates and merge them into the main dictionary.
    button_updates_dict = event_handler_helpers.update_button_states(pil_image)
    all_updates.update(button_updates_dict)

    # 5. Calculate and merge segment display updates.
    # The settings_values_map uses ComponentKey enums as keys.
    video_duration = settings_values_map.get(K.VIDEO_LENGTH_SLIDER, 5.0)
    fps = settings_values_map.get(K.FPS_SLIDER, 30)
    segments_update_dict = event_handler_helpers.ui_update_total_segments(video_duration, fps)
    all_updates.update(segments_update_dict)

    # 6. Return the final, aggregated dictionary of all UI updates.
    return all_updates