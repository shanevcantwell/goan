# ui/queue_processing.py
# Handles interactions with the ProcessingAgent and queue processing logic.

import gradio as gr
import logging
import queue  # For queue.Empty exception
from .queue_manager import queue_manager_instance
from . import shared_state as shared_state_module
from . import queue_helpers
from .agents import ProcessingAgent, ui_update_queue

logger = logging.getLogger(__name__)

def process_task_queue_and_listen(*lora_control_values):
    """Starts the ProcessingAgent, listens for UI updates, and handles stop requests."""
    agent = ProcessingAgent()

    # If processing is already active, this button click is a "stop" request.
    if queue_manager_instance.get_state().get("processing", False):
        # Set the flag for immediate UI feedback via update_button_states
        shared_state_module.shared_state_instance.stop_requested_flag.set()
        agent.send({"type": "stop_queue"})
        gr.Info("Stop requested. The queue will halt after the current task is stopped.")
        # Do not return. Fall through to the listener loop to catch feedback from the agent.
    else:
        # If not processing, this is a "start" request.
        # Clear all state flags at the beginning of a new run.
        # This prevents a "stuck" stop or pause signal from a previous,
        # potentially interrupted, run from immediately terminating the new one.
        shared_state_module.shared_state_instance.interrupt_flag.clear()
        shared_state_module.shared_state_instance.stop_requested_flag.clear()
        shared_state_module.shared_state_instance.preview_request_flag.clear()
        shared_state_module.shared_state_instance.pause_request_flag.clear()
        logger.info("State flags cleared for new queue run.")
        agent.send({
            "type": "start",
            "lora_controls": lora_control_values
        })

    # The listener loop. It doesn't manage state, just streams updates from the agent.
    while True:
        try:
            # Block until an update is available from the agent's UI queue.
            flag, data = ui_update_queue.get(timeout=1.0)

            if flag == "stopping_process":
                # The agent has confirmed it received the stop request.
                # Yield feedback to the user. The button states are handled by the
                # .then() call in the switchboard.
                yield (
                    gr.update(), gr.update(), gr.update(), gr.update(),
                    "Stop signal received. Waiting for current task to halt...",
                    gr.update(), gr.update(), gr.update(), gr.update()
                )
            elif flag == "processing_started":
                # This is the first signal from the agent that it has started.
                # Update the UI to the "processing" state.
                yield (  # The first output (APP_STATE) is gr.update() as we don't modify it here.
                    gr.update(), gr.update(), gr.update(), gr.update(visible=True),
                    gr.update(value="Queue processing started..."),  # Progress description
                    gr.update(value=None, visible=True),  # Progress bar
                    gr.update(interactive=True, value="⏹️ Stop Processing", variant="stop"),  # PROCESS_QUEUE_BUTTON
                    gr.update(interactive=True),  # CREATE_PREVIEW_BUTTON
                    gr.update(interactive=False)  # CLEAR_QUEUE_BUTTON
                )
            elif flag == "progress":
                # Unpack data: task_id, preview_np, desc, html
                _, preview_np, desc, html = data  # type: ignore

                # FIX: Re-evaluate the preview button's state with every progress update.
                # This ensures that after a manual preview request is consumed by the worker
                # (and the flag is cleared), the button re-enables itself on the next update.
                preview_requested = shared_state_module.shared_state_instance.preview_request_flag.is_set()
                preview_button_update = gr.update(
                    interactive=not preview_requested,
                    value="Cancel Preview Request" if preview_requested else "📸 Generate a preview for the currently processing segment",
                    variant="secondary" if preview_requested else "primary"
                )

                yield (
                    gr.update(),  # APP_STATE
                    gr.update(),  # QUEUE_DF
                    gr.update(),  # LAST_FINISHED_VIDEO
                    gr.update(value=preview_np),  # CURRENT_TASK_PREVIEW_IMAGE
                    desc, html, gr.update(), preview_button_update, gr.update()
                )
            elif flag == "file":
                # Unpack data: task_id, new_video_path, _
                _, new_video_path, _ = data  # type: ignore
                yield (gr.update(), gr.update(), gr.update(value=new_video_path), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
            elif flag == "task_starting":
                task = data  # type: ignore
                # This yield was missing the explicit `visible=True` for the progress bar.
                # By adding it, we ensure the bar remains visible when the task starts.
                yield (
                    gr.update(),                                  # APP_STATE
                    queue_helpers.update_queue_df_display(),      # QUEUE_DF
                    gr.update(),                                  # LAST_FINISHED_VIDEO
                    gr.update(),                                  # CURRENT_TASK_PREVIEW_IMAGE
                    f"Processing Task {task['id']}...",            # CURRENT_TASK_PROGRESS_DESCRIPTION
                    gr.update(value=None, visible=True),          # CURRENT_TASK_PROGRESS_BAR
                    gr.update(),                                  # PROCESS_QUEUE_BUTTON
                    gr.update(),                                  # CREATE_PREVIEW_BUTTON
                    gr.update()                                   # CLEAR_QUEUE_BUTTON
                )
            elif flag == "task_finished":
                status = data.get('status')
                task_id = data.get('id')
                final_path = data.get('final_path')

                final_message = f"Task {task_id} {status}."
                if status == 'aborted':
                    final_message = f"Task {task_id} stopped by user."

                # If a final path was provided, update the video player one last time.
                # Otherwise, send a no-op update to preserve its current state.
                video_update = gr.update(value=final_path) if final_path else gr.update()

                yield (
                    gr.update(),
                    queue_helpers.update_queue_df_display(),
                    video_update,
                    gr.update(),
                    final_message, # Progress description
                    gr.update(value=None, visible=False), # Clear progress bar
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            elif flag == "info":
                gr.Info(data)
            elif flag == "queue_finished":
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
    yield (
        gr.update(),
        queue_helpers.update_queue_df_display(),
        gr.update(), # LAST_FINISHED_VIDEO
        gr.update(), # CURRENT_TASK_PREVIEW_IMAGE
        gr.update(value=""), # CURRENT_TASK_PROGRESS_DESCRIPTION
        gr.update(value=None, visible=False), # CURRENT_TASK_PROGRESS_BAR
        gr.update(), # PROCESS_QUEUE_BUTTON
        gr.update(), # CREATE_PREVIEW_BUTTON
        gr.update()  # CLEAR_QUEUE_BUTTON
    )
