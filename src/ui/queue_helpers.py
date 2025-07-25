# ui/queue_helpers.py
# Contains helper functions for queue state management and UI data formatting.

import gradio as gr
import numpy as np
from PIL import Image
import base64
import io
import logging
import json
import zipfile
import html

from .queue_manager import queue_manager_instance
from . import shared_state as shared_state_module
from .enums import ComponentKey as K
from .settings_manager import settings_manager_instance
from . import event_handlers

logger = logging.getLogger(__name__)

def create_queue_zip(zip_file_path: str, queue: list) -> bool:
    """
    Creates a zip archive from a list of queue tasks, including a manifest
    and any associated images.

    Args:
        zip_file_path (str): The full path where the zip file should be saved.
        queue (list): The list of task dictionaries to save.

    Returns:
        bool: True if the zip file was created successfully, False otherwise.
    """
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            queue_manifest = []
            for task in queue:
                params_copy = task['params'].copy()
                input_image_np = params_copy.pop('input_image', None)
                manifest_entry = {"id": task['id'], "params": params_copy, "status": task.get("status", "pending")}
                if input_image_np is not None:
                    img_filename = f"task_{task['id']}_input.png"
                    manifest_entry['image_ref'] = img_filename
                    img = Image.fromarray(input_image_np)
                    with io.BytesIO() as buf:
                        img.save(buf, format='PNG')
                        zf.writestr(img_filename, buf.getvalue())
                queue_manifest.append(manifest_entry)
            zf.writestr(shared_state_module.QUEUE_STATE_JSON_IN_ZIP, json.dumps(queue_manifest, indent=4))
        return True
    except Exception as e:
        logger.error(f"Error creating queue zip file at {zip_file_path}: {e}", exc_info=True)
        return False

def generate_cancel_edit_mode_updates_dict() -> dict:
    """Generates a dictionary of UI updates to reset the UI and exit edit mode."""
    updates = {}

    # Reset main UI controls to their default values
    default_values_map = settings_manager_instance.get_default_values_map()
    for key in shared_state_module.ALL_TASK_UI_KEYS:
        updates[key] = gr.update(value=default_values_map.get(key))

    # Update queue display
    updates[K.QUEUE_DF] = update_queue_df_display()

    # Reset image display
    updates[K.INPUT_IMAGE_DISPLAY] = gr.update(value=None, visible=False)
    updates[K.IMAGE_FILE_INPUT] = gr.update(visible=True, value=None)

    # Get button states for when there is no image and no task being edited
    button_updates = event_handlers.update_button_states(input_image_pil=None)
    updates.update(button_updates)

    return updates

def np_to_base64_uri(np_array_or_tuple, format="png"):
    """Converts a NumPy array to a base64 data URI for embedding in HTML/Markdown."""
    if np_array_or_tuple is None:
        return None
    try:
        # Handle cases where the input might be a raw array or a tuple from other components
        if isinstance(np_array_or_tuple, tuple) and len(np_array_or_tuple) > 0 and isinstance(np_array_or_tuple[0], np.ndarray):
            np_array = np_array_or_tuple[0]
        elif isinstance(np_array_or_tuple, np.ndarray):
            np_array = np_array_or_tuple
        else:
            return None

        pil_image = Image.fromarray(np_array.astype(np.uint8))
        if format.lower() == "jpeg" and pil_image.mode == "RGBA":
            pil_image = pil_image.convert("RGB")

        buffer = io.BytesIO()
        pil_image.save(buffer, format=format.upper())
        img_bytes = buffer.getvalue()
        return f"data:image/{format.lower()};base64,{base64.b64encode(img_bytes).decode('utf-8')}"
    except Exception as e:
        logger.error(f"Error converting NumPy to base64: {e}", exc_info=True)
        return None

def reconstruct_queue_from_zip(zip_filepath: str) -> tuple[list, int]:
    """
    Reconstructs a queue from a saved zip file by reading the manifest
    and reloading associated images.

    Args:
        zip_filepath: The path to the .zip file.

    Returns:
        A tuple containing the reconstructed queue (list of task dicts)
        and the next task ID to use.
    """
    new_queue = []
    max_id = 0
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zf:
            if shared_state_module.QUEUE_STATE_JSON_IN_ZIP not in zf.namelist():
                logger.error(f"Manifest '{shared_state_module.QUEUE_STATE_JSON_IN_ZIP}' not found in zip.")
                return [], 1

            with zf.open(shared_state_module.QUEUE_STATE_JSON_IN_ZIP) as manifest_file:
                queue_manifest = json.load(manifest_file)

            for task_manifest in queue_manifest:
                task_id = task_manifest.get('id', 0)
                if task_id > max_id:
                    max_id = task_id

                params = task_manifest.get('params', {})
                image_ref = task_manifest.get('image_ref')

                if image_ref and image_ref in zf.namelist():
                    with zf.open(image_ref) as img_file:
                        img_bytes = img_file.read()
                        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                        params['input_image'] = np.array(pil_image)

                new_queue.append({"id": task_id, "params": params, "status": "pending"})

        return new_queue, max_id + 1
    except Exception as e:
        logger.error(f"Failed to reconstruct queue from zip '{zip_filepath}': {e}", exc_info=True)
        gr.Warning(f"Error loading queue: {e}")
        return [], 1

def update_queue_df_display():
    """Formats the current queue state into a Gradio DataFrame update object for display."""
    queue_state = queue_manager_instance.get_state()
    queue = queue_state.get("queue", [])
    processing = queue_state.get("processing", False)
    editing_task_id = queue_state.get("editing_task_id") # Define this once here
    total_tasks = len(queue)
    data = []

    def _button_markdown(icon: str, enabled: bool) -> str:
        # ... (this helper function is correct as is)
        if enabled:
            return f"<a href='#' draggable='false' style='text-decoration: none; font-size: 1.2em;'>{icon}</a>"
        else:
            return f"<span style='color: #999; font-size: 1.2em; cursor: not-allowed;'>{icon}</span>"

    for i, task in enumerate(queue):
        params = task['params']
        task_id = task['id']
        status = task.get("status", "pending")

        is_processing_current_task = processing and i == 0
        is_editing_current_task = editing_task_id == task_id
        is_pending = status == 'pending'
        
        # --- Action Button Visibility Logic ---
        # This logic determines if the action icons in the queue are clickable.
        # The backend handlers provide a second layer of enforcement.
        is_first_task = (i == 0)
        is_last_task = (i == total_tasks - 1)

        # # Move controls are disabled entirely if processing is active to prevent race conditions.
        # can_move = is_pending and not processing
        # up_enabled = can_move and not is_first_task
        # down_enabled = can_move and not is_last_task

        # # Pause is only available for the currently processing task.
        # pause_enabled = is_processing_current_task

        # # Edit is punted for this release.
        # edit_enabled = False
        # cancel_enabled = is_pending or is_processing_current_task

        # up_arrow = _button_markdown('⬆️', up_enabled)
        # down_arrow = _button_markdown('⬇️', down_enabled)
        # pause_button = _button_markdown('⏸️', pause_enabled)
        # edit_button = _button_markdown('✎', edit_enabled)
        # cancel_button = _button_markdown('✖️', cancel_enabled)

        # Wrap the full, escaped prompt in a scrollable div. The title attribute provides a native tooltip as a fallback.
        prompt_full_escaped = html.escape(params['prompt'], quote=True)
        prompt_cell = f'<div class="prompt-cell-scrollable" title="{prompt_full_escaped}">{prompt_full_escaped}</div>'

        img_uri = np_to_base64_uri(params.get('input_image'), format="png")
        thumbnail_size = "50px"
        img_md = f'<img draggable="false" src="{img_uri}" alt="Input" style="max-width:{thumbnail_size}; max-height:{thumbnail_size}; display:block; margin:auto; object-fit:contain;" />' if img_uri else ""

        # The status of the task should be the primary source of truth.
        # We check `i == 0` as a safeguard, because only the top task can be processing.
        # This is more robust than relying on the global `processing` flag which can have timing issues.
        if status == "processing" and i == 0: status_display = "⏳ Processing"
        elif is_editing_current_task: status_display = "✏️ Editing" # This takes precedence if a task is somehow being edited.
        elif status == "done": status_display = "✅ Done"
        elif status == "error": status_display = f"❌ Error: {task.get('error_message', 'Unknown')}"
        elif status == "aborted": status_display = "⏹️ Aborted"
        else: status_display = "⏸️ Pending"

        data.append([
            status_display, prompt_cell, img_md, f"{params.get('video_length', 0):.1f}s", task_id
        ])

    # Return an empty DataFrame with the correct headers if the queue is empty
    return gr.update(value=data) if data else gr.update(value=[], headers=["Status", "Prompt", "Image", "Length", "ID"], datatype=["markdown", "markdown", "markdown", "str", "number"], col_count=(5, "dynamic"))