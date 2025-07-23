# ui/queue.py
# This file is the single source of truth for all user-facing queue management logic
# and event handlers. It has been consolidated from queue.py and queue_actions.py
# to eliminate ambiguity and bugs related to duplicated functions.

import gradio as gr
import numpy as np
from PIL import Image
import os
import json
import io
import zipfile # Keep this for save
import tempfile # Keep this for save
import logging

from .queue_manager import queue_manager_instance
from . import shared_state as shared_state_module
from .enums import ComponentKey as K
from . import event_handlers
from .settings_manager import settings_manager_instance
from . import queue_helpers, agents

logger = logging.getLogger(__name__)

# Use a process-specific filename to prevent conflicts between multiple running instances.
AUTOSAVE_FILENAME_PATTERN = "goan_autosave_queue_pid{}.zip"

def autosave_queue_on_exit_action():
    """Saves the current queue to a fixed autosave file on exit."""
    logger.info("Autosaving queue on exit...")
    queue = queue_manager_instance.get_state().get("queue")
    if not queue:
        logger.info("Queue is empty, nothing to autosave.")
        return
    filename = AUTOSAVE_FILENAME_PATTERN.format(os.getpid())
    autosave_path = os.path.join(tempfile.gettempdir(), filename)
    if queue_helpers.create_queue_zip(autosave_path, queue):
        logger.info(f"Successfully autosaved queue with {len(queue)} tasks to {autosave_path}.")
    else:
        logger.error("Failed to autosave queue.")

# This mapping must match the header order in layout.py
ACTION_COLUMN_MAP = {
    0: 'move_up',
    1: 'move_down',
    2: 'pause',
    3: 'edit',
    4: 'cancel'
}

def add_or_update_task_in_queue(*args_from_ui_controls_tuple) -> dict:
    """
    Adds a new task to the queue or updates an existing one if in edit mode.
    Returns a dictionary of UI updates.
    """
    # The first argument is always the input image PIL object.
    input_image_pil = args_from_ui_controls_tuple[0]

    if not input_image_pil:
        gr.Warning("Input image is required!")
        return {}

    # The rest of the arguments are the UI control values.
    all_ui_values_tuple = args_from_ui_controls_tuple[1:]
    # Use ALL_TASK_UI_KEYS to ensure the order and completeness of parameters.
    params_from_ui = dict(zip(shared_state_module.ALL_TASK_UI_KEYS, all_ui_values_tuple))
    base_params_for_worker_dict = {
        worker_key: params_from_ui.get(ui_key) for ui_key, worker_key in shared_state_module.UI_TO_WORKER_PARAM_MAP.items()
    }
    img_np_data = np.array(input_image_pil) # type: ignore

    editing_task_id = queue_manager_instance.get_state().get("editing_task_id")
    if editing_task_id is not None:
        queue_manager_instance.update_task(editing_task_id, base_params_for_worker_dict, img_np_data)
        # After updating, exit edit mode to reset the UI.
        return cancel_edit_mode_action()
    else:
        queue_manager_instance.add_task(base_params_for_worker_dict, img_np_data)
        # After adding, the image is still present. Get button states for that.
        button_updates = event_handlers.update_button_states(input_image_pil=input_image_pil)
        updates = {K.QUEUE_DF: queue_helpers.update_queue_df_display()}
        updates.update(button_updates)
        return updates

def add_resumable_task_from_zip(filepath: str):
    """
    Loads a .goan_resume file, extracts its contents, and adds a new task
    to the queue that is ready to be resumed by the worker.
    """
    logger.info(f"Attempting to load resumable task from: {filepath}")
    if not filepath or not os.path.exists(filepath):
        gr.Warning("Resume file not found.")
        return [gr.update()] * 8 # Return no-op for image drop outputs

    try:
        # Load the parameters from the checkpoint's internal JSON
        resume_state, _ = checkpointing.load_checkpoint(filepath)
        if not resume_state or "params" not in resume_state:
            raise ValueError("Invalid or missing resume state in checkpoint.")
        
        params_for_task = resume_state["params"]
        # CRITICAL: Add the path to the resume file itself to the parameters,
        # so the worker knows which file to load its latent history from.
        params_for_task['resume_latent_path'] = filepath

        # Extract the original source image from the zip archive
        with zipfile.ZipFile(filepath, 'r') as zf:
            with zf.open('source_image.png') as img_file:
                source_image_pil = Image.open(io.BytesIO(img_file.read())).convert("RGBA")
                source_image_np = np.array(source_image_pil)

        # Add the fully formed task to the queue
        queue_manager_instance.add_task(params_for_task, source_image_np)
        gr.Info(f"Resumable task from '{os.path.basename(filepath)}' added to queue.")

        # Return updates to clear the file input and update the queue display
        return gr.update(value=None), queue_helpers.update_queue_df_display()
    except Exception as e:
        gr.Warning(f"Error loading resume file: {e}")
        logger.error(f"Failed to process resume file '{filepath}': {e}", exc_info=True)
        return gr.update(), gr.update()

def cancel_edit_mode_action() -> dict:
    """
    Resets the UI to its default state and exits edit mode.
    This is a thin wrapper around the helper function.
    """
    queue_manager_instance.set_editing_task(None)
    return queue_helpers.generate_cancel_edit_mode_updates_dict()

def handle_queue_action_on_select(evt: gr.SelectData) -> dict:
    """
    Handles user clicks on action icons within the queue DataFrame.
    Returns a dictionary of UI updates.
    """
    if evt.index is None:
        return {}

    row_index, col_index = evt.index

    if col_index not in ACTION_COLUMN_MAP:
        logger.debug(f"Click on non-action column ({col_index}), ignoring.")
        return {}

    action = ACTION_COLUMN_MAP[col_index]
    queue_state = queue_manager_instance.get_state()
    queue = queue_state["queue"]

    if not (0 <= row_index < len(queue)):
        logger.warning(f"Invalid row index {row_index} for queue action.")
        return {}

    task = queue[row_index]
    task_id = task['id']
    status = task.get("status", "pending")
    is_processing = status == 'processing' or (queue_state.get("processing", False) and row_index == 0)
    is_pending = status == 'pending'

    logger.info(f"Queue action '{action}' requested for task {task_id} with status '{status}'.")

    is_processing_globally = queue_state.get("processing", False)

    # --- Backend Enforcement of Disabled State ---
    if action in ['move_up', 'move_down', 'edit'] and not is_pending:
        gr.Info(f"Cannot '{action}' a task that is not 'Pending'.")
        return {}
    if is_processing_globally:
        if action == 'move_up' and row_index <= 1:
            gr.Info("Cannot move a task into the 'currently processing' slot.")
            return {}
        if action in ['move_down', 'edit'] and row_index == 0:
            gr.Info(f"Cannot '{action}' the currently processing task.")
            return {}
    if action == 'pause' and not is_processing:
        gr.Info("Can only pause a task that is currently 'Processing'.")
        return {}

    # --- Handle Action ---
    if action == "move_up":
        queue_manager_instance.move_task('up', row_index)
    elif action == "move_down":
        queue_manager_instance.move_task('down', row_index)
    elif action == "cancel":
        if is_processing:
            # The backend will reset the task's status to 'pending'.
            gr.Info(f"Requesting cancellation for currently processing task {task_id}...")
            agents.ProcessingAgent().send({"type": "cancel_task"})
            # The agent will send UI updates when the task is stopped.
            return {}
        else:
            removed_id = queue_manager_instance.remove_task(row_index)
            if removed_id is not None and queue_state.get("editing_task_id") == removed_id:
                # If we deleted the task we were editing, cancel edit mode.
                return cancel_edit_mode_action()
            # No 'else' here. Let execution fall through to the default update at the end.

    elif action == "edit":
        task_to_edit = queue_manager_instance.get_task_to_edit(row_index)
        if not task_to_edit:
            return {}

        params_to_load_to_ui = task_to_edit['params']
        img_np_from_task = params_to_load_to_ui.get('input_image')

        updates = {K.QUEUE_DF: queue_helpers.update_queue_df_display()}
        for key in shared_state_module.ALL_TASK_UI_KEYS:
            worker_key = shared_state_module.UI_TO_WORKER_PARAM_MAP.get(key)
            updates[key] = gr.update(value=params_to_load_to_ui.get(worker_key))

        updates[K.INPUT_IMAGE_DISPLAY] = gr.update(value=Image.fromarray(img_np_from_task), visible=True) if isinstance(img_np_from_task, np.ndarray) else gr.update(value=None, visible=False)
        updates[K.IMAGE_FILE_INPUT] = gr.update(visible=False)
        button_updates = event_handlers.update_button_states(input_image_pil=Image.fromarray(img_np_from_task) if isinstance(img_np_from_task, np.ndarray) else None)
        updates.update(button_updates)
        return updates
    elif action == "pause":
        gr.Warning(f"In development: Pausing tasks is not yet implemented.")
        return {}

    # Default case: just update the queue display if a move or simple delete happened.
    return {K.QUEUE_DF: queue_helpers.update_queue_df_display()}

def clear_task_queue_action() -> dict:
    """Clears all pending tasks from the queue and returns UI updates as a dictionary."""
    queue_manager_instance.clear_pending_tasks()

    # After clearing, there is no image, so we get button states for that.
    button_updates = event_handlers.update_button_states(input_image_pil=None)

    updates = {K.QUEUE_DF: queue_helpers.update_queue_df_display()}
    updates.update(button_updates)
    return updates

def save_queue_to_zip():
    """Saves the current queue to a zip file."""
    logger.info("Attempting to save queue to zip...")
    queue = queue_manager_instance.get_state().get("queue")
    if not queue:
        gr.Info("Queue is empty. Nothing to save.")
        return gr.update(value=None)
    try:
        # Save the zip to the application's output folder. This directory is known
        # to be accessible by Gradio, which can prevent permission errors when
        # Gradio handles the file for download.
        output_dir = os.path.abspath(settings_manager_instance.outputs_folder)
        os.makedirs(output_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False, suffix=".zip", prefix="queue_save_") as tmp_file:
            temp_zip_path = tmp_file.name
        if queue_helpers.create_queue_zip(temp_zip_path, queue):
            gr.Info(f"Queue with {len(queue)} tasks prepared for download.")
            return gr.update(value=temp_zip_path)
    except Exception as e:
        gr.Warning("Failed to create queue zip file.")
        logger.error(f"Error saving queue to zip: {e}", exc_info=True)
    return gr.update(value=None)

def load_queue_from_zip(zip_file_or_path) -> dict:
    """Loads a queue from a zip file and returns UI updates as a dictionary."""
    filepath = None
    if isinstance(zip_file_or_path, str) and os.path.exists(zip_file_or_path):
        filepath = zip_file_or_path # type: ignore
    elif hasattr(zip_file_or_path, 'name') and zip_file_or_path.name and os.path.exists(zip_file_or_path.name):
        filepath = zip_file_or_path.name

    if not filepath:
        logger.info("No valid queue file found to load.")
        return {} # Return empty dict for no-op

    new_queue, next_id = queue_helpers.reconstruct_queue_from_zip(filepath)
    if new_queue:
        # The responsibility of resetting task status is on the load side.
        # This ensures that any loaded queue is immediately ready for processing, regardless
        # of the statuses saved in the file.
        for task in new_queue:
            task['status'] = 'pending'
        queue_manager_instance.load_queue(new_queue, next_id)
        gr.Info(f"Successfully loaded {len(new_queue)} tasks from {os.path.basename(filepath)}. All tasks set to 'Pending'.")

    # After loading, there is no image selected, so get button states for that.
    button_updates = event_handlers.update_button_states(input_image_pil=None)

    updates = {K.QUEUE_DF: queue_helpers.update_queue_df_display()}
    updates.update(button_updates)
    return updates
