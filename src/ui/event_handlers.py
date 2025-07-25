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
from .queue_manager import queue_manager_instance

LATENT_WINDOW_SIZE = 9  # FramePack standard, for future experimentation

logger = logging.getLogger(__name__)

def safe_shutdown_action(app_state, *ui_values):
    """Performs all necessary save operations to prepare the app for a clean shutdown."""
    logger.info("Performing safe shutdown saves...")
    queue_actions.autosave_queue_on_exit_action()
    workspace_manager.save_ui_and_image_for_refresh(*ui_values)
    gr.Info("Queue and UI state saved. It is now safe to close the terminal.")

def ui_update_total_segments(total_seconds_ui, fps_ui) -> dict:
    """Calculates the number of segments and returns a dictionary update."""

    # Defensively extract the value if the input is a Gradio update dict.
    # This handles cases where Gradio might pass gr.update() objects directly
    # or if the function is called with them from another handler.
    if isinstance(total_seconds_ui, dict) and '__type__' in total_seconds_ui and total_seconds_ui['__type__'] == 'update':
        total_seconds_ui = total_seconds_ui.get('value')
    if isinstance(fps_ui, dict) and '__type__' in fps_ui and fps_ui['__type__'] == 'update':
        fps_ui = fps_ui.get('value')

    latent_window_size = LATENT_WINDOW_SIZE
    try:
        logger.debug(f"ui_update_total_segments received: total_seconds_ui={total_seconds_ui}, fps_ui={fps_ui} (latent_window_size={latent_window_size})")
        total_frames = int(total_seconds_ui * fps_ui)
        frames_per_segment = latent_window_size * 4 - 3
        total_segments = int(max(round(total_frames / frames_per_segment), 1)) if frames_per_segment > 0 else 1
        update_text = f"Calculated: {total_segments} Segments, {total_frames} Total Frames"
    except (TypeError, ValueError):
        logger.error(f"Error in ui_update_total_segments. Inputs: total_seconds_ui={total_seconds_ui}, fps_ui={fps_ui}", exc_info=True)
        update_text = "Segments: Invalid input"
    return {K.TOTAL_SEGMENTS_DISPLAY: gr.update(value=update_text)}

def update_variable_cfg_controls_visibility(cfg_shape_value: str, cfg_start_value: float) -> dict:
    """
    Updates visibility and interactivity of CFG sliders based on the selected shape.
    Also resets the end CFG value to match the start value when variable CFG is turned off.
    """
    is_linear = cfg_shape_value == "Linear"
    is_roll_off = cfg_shape_value == "Roll-off"

    # DISTILLED_CFG_END_SLIDER is visible and interactive for both Linear and Roll-off
    end_cfg_active = is_linear or is_roll_off

    # When variable CFG is off, the end value should match the start value.
    # Otherwise, it retains its current value (no-op update).
    end_cfg_update_value = cfg_start_value if not end_cfg_active else gr.update()

    return {
        K.DISTILLED_CFG_END_SLIDER: gr.update(visible=end_cfg_active, interactive=end_cfg_active, value=end_cfg_update_value),
        K.ROLL_OFF_START_SLIDER: gr.update(visible=is_roll_off, interactive=is_roll_off),
        K.ROLL_OFF_FACTOR_SLIDER: gr.update(visible=is_roll_off, interactive=is_roll_off),
    }


def handle_image_upload(temp_file_data: any) -> dict:
    """
    Consolidated handler for image uploads. It processes the image, extracts
    metadata, and updates all relevant UI components, including button states.
    """
    updates = {}
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
    button_updates = update_button_states(pil_image)
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
    button_updates = update_button_states(input_image_pil=None)
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
    final_updates.update(ui_update_total_segments(new_video_len, new_fps))

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
    return update_button_states(input_image_pil)

# Define the button keys in a fixed order for consistent output.
BUTTON_KEYS = [
    K.ADD_TASK_BUTTON,
    K.PROCESS_QUEUE_BUTTON,
    K.CREATE_PREVIEW_BUTTON,
    K.CLEAR_IMAGE_BUTTON,
    K.DOWNLOAD_IMAGE_BUTTON,
    K.SAVE_QUEUE_BUTTON,
    K.CLEAR_QUEUE_BUTTON,
]

def get_button_state_outputs(components: dict) -> list:
    """Returns the list of button components for state updates."""
    return [components[key] for key in BUTTON_KEYS]

def update_button_states(input_image_pil):
    """
    Updates button states based on a declarative rules engine. This function
    is the single source of truth for the state of all major control buttons.
    """
    # 1. Derive the current application state from the inputs.
    # This function intentionally does not use app_state or queue_df_data from the UI,
    # as it gets the most up-to-date state directly from the singleton manager.
    queue_state = queue_manager_instance.get_state()
    is_editing = queue_state.get("editing_task_id") is not None
    is_processing = queue_state.get("processing", False)
    is_editing_processing_task = is_editing and is_processing and queue_state.get("queue") and queue_state["editing_task_id"] == queue_state["queue"][0]["id"]

    # Check if a stop has been requested (e.g., by clicking "Stop Processing")
    stop_requested = shared_state_module.shared_state_instance.stop_requested_flag.is_set()

    state = {
        'stop_requested': stop_requested, # Use the flag
        'is_editing': is_editing,
        'is_processing': is_processing,
        'is_editing_processing_task': is_editing_processing_task,
        'has_image': input_image_pil is not None,
        'queue_has_tasks': bool(queue_state.get("queue", [])),
        'has_pending_tasks': any(task.get("status", "pending") == "pending" for task in queue_state.get("queue", [])),
        'preview_requested': shared_state_module.shared_state_instance.preview_request_flag.is_set(),
    }

    # 2. Define the rules as a list of condition->updates mappings.
    # The first rule with a condition that returns True will be used.
    rules = [
        {'condition': lambda s: s['stop_requested'], 'get_updates': lambda s: {
            K.PROCESS_QUEUE_BUTTON: gr.update(interactive=True, 
                value="🫸 Stopping...", variant="stop"),
            K.ADD_TASK_BUTTON: gr.update(interactive=True),
            K.CREATE_PREVIEW_BUTTON: gr.update(interactive=False),
            K.CLEAR_IMAGE_BUTTON: gr.update(interactive=True),
            K.DOWNLOAD_IMAGE_BUTTON: gr.update(interactive=True),
            K.SAVE_QUEUE_BUTTON: gr.update(interactive=False),
            K.CLEAR_QUEUE_BUTTON: gr.update(interactive=False),
        }},
        {'condition': lambda s: s['is_editing'], 'get_updates': lambda s: {
            K.ADD_TASK_BUTTON: gr.update(interactive=not s['is_editing_processing_task'], variant="primary"),
            K.PROCESS_QUEUE_BUTTON: gr.update(interactive=False, 
                value="▶️ Process Queue", variant="secondary"),
            K.CREATE_PREVIEW_BUTTON: gr.update(interactive=False, variant="secondary"),
            K.CLEAR_IMAGE_BUTTON: gr.update(interactive=False, variant="secondary"),
            K.DOWNLOAD_IMAGE_BUTTON: gr.update(interactive=False, variant="secondary"),
            K.SAVE_QUEUE_BUTTON: gr.update(interactive=False, variant="secondary"),
            K.CLEAR_QUEUE_BUTTON: gr.update(interactive=False, variant="secondary"),
        }},
        {'condition': lambda s: s['is_processing'], 'get_updates': lambda s: {
            K.PROCESS_QUEUE_BUTTON: gr.update(interactive=True, 
                value="⏹️ Stop Processing", variant="stop"),
            K.CREATE_PREVIEW_BUTTON: gr.update(interactive=not s['preview_requested'],
                value="Cancel Preview Request" if s['preview_requested'] else 
                      "📸 Generate a preview for the currently processing segment",
                variant="secondary" if s['preview_requested'] else "primary"),
            K.CLEAR_QUEUE_BUTTON: gr.update(interactive=s['has_pending_tasks'], variant="stop" if s['has_pending_tasks'] else "secondary"),
            K.ADD_TASK_BUTTON: gr.update(interactive=s['has_image'], variant="primary" if s['has_image'] else "secondary"),
            K.CLEAR_IMAGE_BUTTON: gr.update(interactive=s['has_image'], variant="secondary"),
            K.DOWNLOAD_IMAGE_BUTTON: gr.update(interactive=s['has_image'], variant="secondary"),
            K.SAVE_QUEUE_BUTTON: gr.update(interactive=s['queue_has_tasks'], variant="primary"),
        }},
        # Default rule for idle state.
        {'condition': lambda s: True, 'get_updates': lambda s: {
            K.ADD_TASK_BUTTON: gr.update(interactive=s['has_image'], variant="primary" if s['has_image'] else "secondary"),
            K.PROCESS_QUEUE_BUTTON: gr.update(interactive=s['queue_has_tasks'],
                value="▶️ Process Queue", variant="primary"),
            K.CREATE_PREVIEW_BUTTON: gr.update(interactive=False, variant="secondary"),
            K.CLEAR_IMAGE_BUTTON: gr.update(interactive=s['has_image'], variant="secondary"),
            K.DOWNLOAD_IMAGE_BUTTON: gr.update(interactive=s['has_image'], variant="secondary"),
            K.SAVE_QUEUE_BUTTON: gr.update(interactive=s['queue_has_tasks'], variant="primary"),
            K.CLEAR_QUEUE_BUTTON: gr.update(interactive=s['has_pending_tasks'], variant="stop" if s['has_pending_tasks'] else "secondary"),
        }},
    ]

    # 3. Find the first matching rule and get its updates dictionary.
    updates_dict = {}
    for rule in rules:
        if rule['condition'](state):
            updates_dict = rule['get_updates'](state)
            break

    # 4. Return the updates tuple in the correct, fixed order.
    # Return a dictionary with updates for all buttons, using no-op for unspecified ones.
    return {key: updates_dict.get(key, gr.update()) for key in BUTTON_KEYS}
