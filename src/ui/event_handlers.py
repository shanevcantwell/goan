import gradio as gr
import time
import os
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

# The fixed filename used for saving the image on session unload/refresh.
REFRESH_IMAGE_FILENAME = "goan_refresh_image.png"

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
                # Check if this is the automatic session restore image.
                is_session_restore = os.path.basename(filepath) == REFRESH_IMAGE_FILENAME

                if is_session_restore:
                    # If it's a session restore, apply the metadata directly without a modal.
                    logger.info("Session restore image detected. Applying metadata automatically.")
                    creative_params = metadata_manager.ui_load_params_from_image_metadata(params)
                    updates.update({key: gr.update(value=value) for key, value in creative_params.items()})
                else:
                    # For a manual upload, trigger the confirmation modal.
                    logger.info("Manual image upload with metadata detected. Triggering confirmation modal.")
                    updates[K.EXTRACTED_METADATA_STATE] = params
                    updates[K.METADATA_PROMPT_PREVIEW] = params.get('prompt', '')
                    updates[K.METADATA_MODAL_TRIGGER_STATE] = gr.update(value=str(time.time()))
        except Exception as e:
            gr.Warning(f"Could not load file '{os.path.basename(filepath)}' as an image: {e}")
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

def handle_confirm_metadata(metadata_dict, current_video_len, current_fps, latent_window_size_ui) -> dict:
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

    #    Then, calculate and merge the segment display updates.
    #    We must manually merge the gr.update() objects for the video length slider to preserve
    #    both the 'value' from metadata and the 'info' text from the calculation.
    #    A simple dict.update() would overwrite one with the other.
    segments_update_dict = helpers.ui_update_total_segments(new_video_len, new_fps, latent_window_size_ui)
    slider_update_from_metadata = final_updates.get(K.VIDEO_LENGTH_SLIDER, gr.update())
    slider_update_from_segments = segments_update_dict.get(K.VIDEO_LENGTH_SLIDER, gr.update())
    
    combined_attrs = {}
    # A gr.update() object is a dictionary. We check for its type marker and merge its contents.
    if isinstance(slider_update_from_metadata, dict) and slider_update_from_metadata.get('__type__') == 'update':
        combined_attrs.update({k: v for k, v in slider_update_from_metadata.items() if k != '__type__'})

    if isinstance(slider_update_from_segments, dict) and slider_update_from_segments.get('__type__') == 'update':
        combined_attrs.update({k: v for k, v in slider_update_from_segments.items() if k != '__type__'})

    final_updates[K.VIDEO_LENGTH_SLIDER] = gr.update(**combined_attrs)

    #    Finally, add the modal close update.
    final_updates[K.METADATA_MODAL_TRIGGER_STATE] = gr.update(value=None) # Close modal
    return final_updates

def prepare_image_for_download(pil_image, lora_name, lora_weight, lora_targets, *creative_values):
    """Injects creative and LoRA parameter metadata into the current image and prepares it for download."""
    if not isinstance(pil_image, Image.Image):
        gr.Warning("No valid image to download.")
        return None

    # Create the parameters dictionary from the creative UI controls.
    params_dict = metadata_manager.create_params_from_ui(shared_state_module.CREATIVE_UI_KEYS, creative_values)

    # Add LoRA settings if a LoRA is active, following the schema from the design doc.
    if lora_name and lora_name != "None":
        params_dict["loras"] = [
            {
                "name": lora_name,
                "weight": lora_weight,
                "targets": lora_targets,
            }
        ]

    pnginfo_obj = metadata_manager.create_pnginfo_obj(params_dict)
    image_copy = pil_image.copy() # Use a copy to avoid modifying the displayed image's info
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
        image_copy.save(tmp_file.name, "PNG", pnginfo=pnginfo_obj)
        gr.Info("Image with current settings prepared for download.")
        return gr.update(value=tmp_file.name)
    
def handle_stop_queue_request():
    """
    Handles the user request to stop the entire processing queue.
    This is a dedicated handler for the "Stop Processing" button click.
    """
    from .enums import UIMessage
    from .agents import ProcessingAgent
    agent = ProcessingAgent()
    
    # Set the flag for immediate UI feedback via update_button_states
    shared_state_module.shared_state_instance.stop_requested_flag.set()
    
    # Send the message to the agent to initiate the stop sequence.
    agent.send((UIMessage.STOP_QUEUE, None))
    
    gr.Info("Stop signal sent. The queue will halt after the current task is stopped.")
    
    # Return an update for the UI description to give immediate feedback.
    return {
        K.CURRENT_TASK_PROGRESS_DESCRIPTION: "Stop signal sent. Waiting for current task to halt..."
    }

def toggle_manual_preview_action(input_image_pil):
    """
    Toggles the manual preview request flag in shared state.
    Returns a dictionary of button state updates.
    """
    if not queue_manager_instance.get_state().get("processing", False):
        gr.Warning("Cannot request preview when processing is not active.")
        return helpers.update_button_states(input_image_pil)

    if shared_state_module.shared_state_instance.preview_request_flag.is_set():
        gr.Info("Preview generation has already been requested.")
    else:
        logger.info("Manual preview requested. Setting flag and sending signal to agent.")
        shared_state_module.shared_state_instance.preview_request_flag.set()

        # In addition to setting the flag for optimistic UI updates, we must
        # send a message to the agent's processing loop to trigger the action.
        from .agents import ProcessingAgent
        from .enums import UIMessage
        agent = ProcessingAgent()
        agent.send((UIMessage.REQUEST_PREVIEW, None))
        gr.Info("Preview generation requested.")

    # Return a dictionary of updates for all buttons.
    # This will reflect the "requested" state immediately.
    return helpers.update_button_states(input_image_pil)
