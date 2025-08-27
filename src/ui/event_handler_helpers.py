import gradio as gr
import logging

from .enums import ComponentKey as K
from .queue_manager import queue_manager_instance
from . import shared_state as shared_state_module

logger = logging.getLogger(__name__)

LATENT_WINDOW_SIZE = 9  # FramePack standard, for future experimentation

def _get_value_from_input(input_val: any) -> any:
    """
    Safely extracts the 'value' from a Gradio input, which could be a raw
    value or a gr.update() dictionary, a common case in chained events.
    """
    if isinstance(input_val, dict) and input_val.get('__type__') == 'update':
        return input_val.get('value')
    return input_val

def _merge_gradio_updates(*update_dicts: dict) -> gr.update:
    """Merges multiple Gradio update dictionaries into a single gr.update object."""
    combined_attrs = {}
    for update_dict in update_dicts:
        if isinstance(update_dict, dict) and update_dict.get('__type__') == 'update':
            # Exclude the internal type marker from the merge
            combined_attrs.update({k: v for k, v in update_dict.items() if k != '__type__'})
    return gr.update(**combined_attrs)

def ui_update_total_segments(total_seconds_ui, fps_ui, latent_window_size_ui) -> dict:
    """Calculates the number of segments and returns a dictionary update for the video length slider's label property."""
    total_seconds_ui = _get_value_from_input(total_seconds_ui)
    fps_ui = _get_value_from_input(fps_ui)
    latent_window_size = _get_value_from_input(latent_window_size_ui)

    frames_per_segment = latent_window_size * 4 - 3

    try:
        logger.debug(f"ui_update_total_segments received: total_seconds_ui={total_seconds_ui}, fps_ui={fps_ui} (latent_window_size={latent_window_size})")
        total_frames = int(total_seconds_ui * fps_ui)
        total_segments = int(max(round(total_frames / frames_per_segment), 1)) if frames_per_segment > 0 else 1
        update_text = f"{total_seconds_ui}sec: {total_segments} Segments, {total_frames} Total Frames"

    except (TypeError, ValueError):
        logger.error(f"Error in ui_update_total_segments. Inputs: total_seconds_ui={total_seconds_ui}, fps_ui={fps_ui}", exc_info=True)
        update_text = "Segments: Invalid input"
    return {K.VIDEO_LENGTH_SLIDER: gr.update(label=update_text)}

def update_variable_cfg_controls_visibility(cfg_shape_value: str, cfg_start_value: float) -> dict:
    """
    Updates visibility and interactivity of CFG sliders based on the selected shape.
    Also resets the end CFG value to match the start value when variable CFG is turned off.
    """
    cfg_shape_value = _get_value_from_input(cfg_shape_value)
    cfg_start_value = _get_value_from_input(cfg_start_value)
    logger.debug(f"Updating CFG visibility for shape: '{cfg_shape_value}'")

    is_roll_off = (cfg_shape_value == "Roll-off")
    is_variable_cfg_active = (cfg_shape_value != "Off") # True for "Linear" and "Roll-off"

    updates = {
        # The "Roll-off" sliders are only visible and interactive for the "Roll-off" shape.
        K.ROLL_OFF_START_SLIDER: gr.update(visible=is_roll_off, interactive=is_roll_off),
        K.ROLL_OFF_FACTOR_SLIDER: gr.update(visible=is_roll_off, interactive=is_roll_off),
    }

    # Conditionally create the update for the End slider to avoid nested gr.update() objects.
    if is_variable_cfg_active:
        # When variable CFG is active, the end slider is visible and interactive.
        # Its value should NOT be changed when the start slider is adjusted, so we
        # create an update object without the `value` parameter.
        end_slider_update = gr.update(visible=True, interactive=True)
    else:
        # When variable CFG is off, the end slider is hidden and its value
        # is reset to match the start slider's value.
        end_slider_update = gr.update(visible=False, interactive=False, value=cfg_start_value)

    updates[K.DISTILLED_CFG_END_SLIDER] = end_slider_update
    return updates

def handle_settings_menu_change(selected_menu: list | None, app_state: dict) -> dict:
    """
    Handles changes in the settings menu to toggle visibility of settings groups
    and correctly show/hide the appropriate video player, ensuring the video
    path is always correctly loaded.

    Args:
        selected_menu (list | None): The list of selected checkboxes (0 or 1 item).
        app_state (dict): The current application state, containing the last video path.

    Returns:
        dict: A dictionary of gr.update() objects to show/hide the groups and
              to enforce the single-selection state in the UI.
    """
    active_menu = "Off"
    update_value = []
    last_video_path = app_state.get("last_completed_video_path")

    if selected_menu:
        # If multiple items are selected (e.g., user checks a second box),
        # treat the last one in the list as the new, single selection.
        active_menu = selected_menu[-1]
        update_value = [active_menu]
    
    is_settings_open = (active_menu != "Off")

    return {
        K.POWER_USER_GROUP: gr.update(visible=(active_menu == "Power User")), # type: ignore
        K.LORA_GROUP: gr.update(visible=(active_menu == "LoRA")),
        K.ADVANCED_SETTINGS_GROUP: gr.update(visible=(active_menu == "Advanced")),
        # Show the small, 2-column video player when a setting menu is open.
        K.LAST_FINISHED_VIDEO: gr.update(visible=is_settings_open, value=last_video_path),
        # Show the full-width video player when all settings are closed.
        K.FULL_WIDTH_LAYOUT_ROW: gr.update(visible=not is_settings_open),
        K.LAST_FINISHED_VIDEO_FULL_WIDTH: gr.update(value=last_video_path),
        # Enforce single selection in the UI by updating its value
        K.SETTINGS_MENU_CHECKBOX_GROUP: gr.update(value=update_value)
    }

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