# ui/queue_processing.py
# Handles interactions with the ProcessingAgent and queue processing logic.

import gradio as gr
import logging
import queue  # For queue.Empty exception
from .queue_manager import queue_manager_instance
from . import shared_state as shared_state_module
from . import queue_helpers
from .agents import ProcessingAgent, ui_update_queue
from .enums import ComponentKey as K, UIMessage


logger = logging.getLogger(__name__)

def create_update_tuple(updates: dict) -> tuple:
    """
    Converts a dictionary of {ComponentKey: gr.update} into a tuple
    ordered according to the single source of truth, QUEUE_PROCESSING_OUTPUT_KEYS.
    Any component key not in the input dictionary will get a no-op gr.update().
    """
    return tuple(updates.get(key, gr.update()) for key in shared_state_module.QUEUE_PROCESSING_OUTPUT_KEYS)


def process_task_queue_and_listen(app_state: dict, *lora_control_values):
    """Starts the ProcessingAgent, listens for UI updates, and handles stop requests."""
    agent = ProcessingAgent()

    # Add a guard clause to prevent this from running if processing is already active.
    # This is part of the "one-click start/stop" logic.
    if queue_manager_instance.get_state().get("processing", False):
        return create_update_tuple({}) # Return a no-op update tuple

    # This function is now only for starting the queue. The stop logic is handled
    # by a separate, dedicated event handler.
    # Clear all state flags at the beginning of a new run.
    shared_state_module.shared_state_instance.interrupt_flag.clear()
    shared_state_module.shared_state_instance.stop_requested_flag.clear()
    shared_state_module.shared_state_instance.preview_request_flag.clear()
    shared_state_module.shared_state_instance.pause_request_flag.clear()
    logger.info("State flags cleared for new queue run. Sending 'start' to agent.")
    agent.send((UIMessage.START, {
        "lora_controls": lora_control_values
    }))

    # The listener loop. It doesn't manage state, just streams updates from the agent.
    while True:
        try:
            # Block until an update is available from the agent's UI queue.
            flag, data = ui_update_queue.get(timeout=1.0)

            if flag == UIMessage.STOPPING_PROCESS:
                # The agent has confirmed it received the stop request.
                # Yield feedback to the user. The button states are handled by the
                # final yield after the loop.
                updates = {
                    K.CURRENT_TASK_PROGRESS_DESCRIPTION: "Stop signal received. Waiting for current task to halt..."
                }
                yield create_update_tuple(updates)

            elif flag == UIMessage.PROCESSING_STARTED:
                # This is the first signal from the agent that it has started.
                # Update the UI to the "processing" state.
                updates = {
                    K.CURRENT_TASK_PREVIEW_IMAGE: gr.update(visible=True),
                    K.CURRENT_TASK_PROGRESS_DESCRIPTION: gr.update(value="Queue processing started..."),
                    K.CURRENT_TASK_PROGRESS_BAR: gr.update(value=None, visible=True),
                    K.PROCESS_QUEUE_BUTTON: gr.update(value="⏹️ Stop Processing", interactive=True, variant="stop"),
                    K.CREATE_PREVIEW_BUTTON: gr.update(interactive=True),
                    K.CLEAR_QUEUE_BUTTON: gr.update(interactive=False)
                }
                yield create_update_tuple(updates)

            elif flag == UIMessage.PROGRESS:
                # Worker messages ('progress') now send a dictionary payload.
                if not isinstance(data, dict):
                    logger.warning(f"Received 'progress' message with unexpected data type: {type(data)}. Expected dict. Skipping update.")
                    continue

                preview_np = data.get("preview_np")
                desc = data.get("description", "")
                html = data.get("html", "")
                current_segment = data.get("current_segment", 0)
                preview_frequency = data.get("preview_frequency", 0)
                # The worker sends 'preview_specified_segments', which can be the raw value.
                # The UI logic expects a string.
                preview_specified_segments_str = str(data.get("preview_specified_segments", ""))
                eta_display = data.get("eta_display", "")

                # FIX: Re-evaluate the preview button's state with every progress update.
                # This ensures that after a manual preview request is consumed by the worker
                # (and the flag is cleared), the button re-enables itself on the next update.
                preview_requested = shared_state_module.shared_state_instance.preview_request_flag.is_set()

                # --- Determine if a preview is being generated automatically ---
                is_automatic_preview = False
                # Check frequency-based preview (safe check for frequency > 0)
                if preview_frequency > 0 and current_segment % preview_frequency == 0:
                    is_automatic_preview = True
                # Check specified-segment preview
                if preview_specified_segments_str and not is_automatic_preview:
                    try:
                        parsed_segments = {int(s.strip()) for s in preview_specified_segments_str.split(',') if s.strip()}
                        if current_segment in parsed_segments:
                            is_automatic_preview = True
                    except ValueError:
                        logger.warning(f"Could not parse preview_specified_segments: '{preview_specified_segments_str}'")

                preview_generating = preview_requested or is_automatic_preview
                preview_button_update = gr.update(
                    interactive=not preview_requested,
                    value="📸 Preview generation requested" if preview_generating else "📸 Generate a preview for the currently processing segment",
                    variant="secondary" if preview_requested else "primary"
                )

                updates = {
                    K.CURRENT_TASK_PREVIEW_IMAGE: gr.update(value=preview_np),
                    K.CURRENT_TASK_PROGRESS_DESCRIPTION: gr.update(value=desc),
                    K.CURRENT_TASK_PROGRESS_BAR: gr.update(value=html),
                    K.SEGMENT_ETA_DISPLAY: gr.update(value=eta_display),
                    K.CREATE_PREVIEW_BUTTON: preview_button_update,
                }
                yield create_update_tuple(updates)

            elif flag == UIMessage.FILE:
                # The 'file' message payload is a tuple: (task_id, path, message)
                if not isinstance(data, dict):
                    logger.warning(f"Received 'file' message with malformed data: {data}")
                    continue

                new_video_path = data.get('path')
                if not new_video_path:
                    logger.warning(f"Received 'file' message but could not extract a path from data: {data!r}")
                    continue

                app_state["last_completed_video_path"] = new_video_path
                updates = {
                    K.APP_STATE: gr.update(value=app_state),
                    K.LAST_FINISHED_VIDEO: gr.update(value=new_video_path),
                    K.LAST_FINISHED_VIDEO_FULL_WIDTH: gr.update(value=new_video_path),
                }
                yield create_update_tuple(updates)

            elif flag == UIMessage.TASK_STARTING:
                task = data  # type: ignore
                updates = {
                    K.QUEUE_DF: queue_helpers.update_queue_df_display(),
                    K.CURRENT_TASK_PROGRESS_DESCRIPTION: gr.update(value=f"Processing Task {task['id']}..."),
                    K.CURRENT_TASK_PROGRESS_BAR: gr.update(value=None, visible=True),
                }
                yield create_update_tuple(updates)

            elif flag == UIMessage.TASK_FINISHED:
                # The 'task_finished' message payload is a dictionary.
                if isinstance(data, dict):
                    status = data.get('status')
                    task_id = data.get('id')
                    final_path = data.get('final_path')

                    final_message = f"Task {task_id} {status}."
                    if status == 'aborted':
                        final_message = f"Task {task_id} stopped by user."

                    # If a final path was provided, update the video player one last time.
                    # Otherwise, send a no-op update to preserve its current state.
                    video_update = gr.update(value=final_path) if final_path else gr.update()
                    if final_path:
                        app_state["last_completed_video_path"] = final_path

                    updates = {
                        K.APP_STATE: gr.update(value=app_state),
                        K.QUEUE_DF: queue_helpers.update_queue_df_display(),
                        K.LAST_FINISHED_VIDEO: video_update,
                        K.CURRENT_TASK_PROGRESS_DESCRIPTION: gr.update(value=final_message),
                        K.CURRENT_TASK_PROGRESS_BAR: gr.update(value=None, visible=False),
                    }
                    yield create_update_tuple(updates)
                else:
                    logger.warning(f"Received 'task_finished' message with malformed data: {data}")

            elif flag == UIMessage.INFO:
                gr.Info(data)
            elif flag == UIMessage.QUEUE_FINISHED:
                # The agent has signaled the end of all processing.
                logger.info("UI listener received 'queue_finished' signal. Exiting loop.")
                break

        except queue.Empty:
            # If the queue is empty, we check if the agent is still processing.
            # If not, it means the process finished or was stopped without a final signal.
            if not queue_manager_instance.get_state().get("processing", False):
                logger.info("UI listener detected processing has stopped. Exiting loop.")
                break
            continue  # Continue waiting for updates.

    # The .then() call in the switchboard will handle the final button state update.
    # We just need to yield one last time to ensure the final queue state is displayed.
    logger.info("UI listener loop finished. Yielding final queue display.")
    final_updates = {
        K.QUEUE_DF: queue_helpers.update_queue_df_display(),
        K.CURRENT_TASK_PROGRESS_DESCRIPTION: gr.update(value=""),
        K.CURRENT_TASK_PROGRESS_BAR: gr.update(value=None, visible=False),
    }
    yield create_update_tuple(final_updates)
