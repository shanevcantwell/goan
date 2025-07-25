import gradio as gr
import time
import tempfile
from PIL import Image, PngImagePlugin

import logging
from . import metadata as metadata_manager
from . import shared_state as shared_state_module
from . import workspace as workspace_manager
from . import queue as queue_actions # Use queue.py as the source for actions
from .enums import ComponentKey as K
from . import event_handler_helpers as helpers
from .queue_manager import queue_manager_instance

logger = logging.getLogger(__name__)

def safe_shutdown_action(app_state, *ui_values):
    """Performs all necessary save operations to prepare the app for a clean shutdown."""
    logger.info("Performing safe shutdown saves...")
    queue_actions.autosave_queue_on_exit_action()
    workspace_manager.save_ui_and_image_for_refresh(*ui_values)
    gr.Info("Queue and UI state saved. It is now safe to close the terminal.")

def handle_image_upload(temp_file_data: any) -> dict:
    """
    Consolidated handler for image uploads. It processes the image, extracts
    metadata, and updates all relevant UI components, including button states.
    """
    updates = {
        # Always clear previous metadata state when a new image is loaded.
        K.EXTRACTED_METADATA_STATE: {}
    }
    pil_image = None
    filepath = None

    if isinstance(temp_file_data, str):
        filepath = temp_file_data
    elif hasattr(temp_file_data, 'name'):
        filepath = temp_file_data.name

    if filepath:
        try:
            pil_image = Image.open(filepath)
            updates[K.INPUT_IMAGE_DISPLAY] = gr.update(value=pil_image, visible=True)
            updates[K.IMAGE_FILE_INPUT] = gr.update(visible=False)

            params = metadata_manager.extract_metadata_from_pil_image(pil_image)
            if params:
                updates[K.EXTRACTED_METADATA_STATE] = params
                updates[K.METADATA_PROMPT_PREVIEW] = params.get('prompt', '')
                updates[K.METADATA_MODAL_TRIGGER_STATE] = gr.update(value=str(time.time()))
        except Exception as e:
            gr.Warning(f"Could not load file as an image: {e}")
            pil_image = None # Ensure image is None on failure
            updates[K.INPUT_IMAGE_DISPLAY] = gr.update(value=None, visible=False)
            updates[K.IMAGE_FILE_INPUT] = gr.update(visible=True, value=None)

    # Update button states based on whether an image is present
    button_updates = helpers.update_button_states(pil_image)
    updates.update(button_updates)
    return updates

def handle_clear_image() -> dict:
    """
    Consolidated handler for clearing the image. It resets the image UI
    and updates all relevant button states.
    """
    updates = {
        K.IMAGE_FILE_INPUT: gr.update(value=None, visible=True),
        K.INPUT_IMAGE_DISPLAY: gr.update(visible=False, value=None),
        K.EXTRACTED_METADATA_STATE: {}
    }
    # Get the button states for when there is no image
    button_updates = helpers.update_button_states(input_image_pil=None)
    updates.update(button_updates)
    return updates

def handle_confirm_metadata(metadata_dict, current_video_len, current_fps) -> dict:
    """
    Consolidated handler for applying image metadata. It updates creative UI,
    recalculates segments, and closes the modal.
    """
    # 1. Get a dictionary of raw, typed parameter values from the metadata.
    #    The `ui_load_params_from_image_metadata` function is responsible for
    #    parsing and type-casting the values from the image's metadata dict.
    creative_params_from_metadata = metadata_manager.ui_load_params_from_image_metadata(metadata_dict)

    # 2. Determine the new values for segment calculation
    #    Use the value from metadata if present, otherwise use the current UI value.
    #    This is safe because creative_params_from_metadata contains raw values.
    new_video_len = creative_params_from_metadata.get(K.VIDEO_LENGTH_SLIDER, current_video_len)
    new_fps = creative_params_from_metadata.get(K.FPS_SLIDER, current_fps)

    # 3. Combine all updates
    #    First, convert the dictionary of raw parameters into a dictionary of gr.update() objects.
    final_updates = {key: gr.update(value=value) for key, value in creative_params_from_metadata.items()}

    #    Then, add the segment calculation updates.
    final_updates.update(helpers.ui_update_total_segments(new_video_len, new_fps))

    #    Finally, add the modal close update.
    final_updates[K.METADATA_MODAL_TRIGGER_STATE] = gr.update(value=None) # Close modal
    return final_updates

def prepare_image_for_download(pil_image, *creative_values):
    """Injects creative parameter metadata into the current image and prepares it for download."""
    if not isinstance(pil_image, Image.Image):
        gr.Warning("No valid image to download.")
        return None

    # Create the parameters dictionary from the creative UI controls.
    params_dict = metadata_manager.create_params_from_ui(shared_state_module.CREATIVE_UI_KEYS, creative_values)

    pnginfo_obj = metadata_manager.create_pnginfo_obj(params_dict)
    image_copy = pil_image.copy() # Use a copy to avoid modifying the displayed image's info
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
        image_copy.save(tmp_file.name, "PNG", pnginfo=pnginfo_obj)
        gr.Info("Image with current settings prepared for download.")
        return gr.update(value=tmp_file.name)

def optimistic_process_button_update():
    """
    Provides immediate feedback on the Process/Stop button.
    Checks the current processing state to decide whether to show
    "Starting..." or "Stopping...". This is an optimistic UI update.
    """
    if queue_manager_instance.get_state().get("processing", False):
        # We are currently processing, so this click is a STOP request.
        # The stop_requested_flag is set in the main handler. We just update the UI.
        return gr.update(interactive=False, value="Stopping...", variant="stop")
    else:
        # We are not processing, so this click is a START request.
        return gr.update(interactive=False, value="Starting...", variant="secondary")

def toggle_manual_preview_action(input_image_pil):
    """
    Toggles the manual preview request flag in shared state.
    Returns a dictionary of button state updates.
    """
    if shared_state_module.shared_state_instance.preview_request_flag.is_set():
        shared_state_module.shared_state_instance.preview_request_flag.clear()
    else:
        shared_state_module.shared_state_instance.preview_request_flag.set()
    # Return a dictionary of updates for all buttons.
    return helpers.update_button_states(input_image_pil)
