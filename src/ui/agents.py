# ui/agents.py
import threading
import queue
import logging
import traceback
import numpy as np

from core.generation_core import worker
from diffusers_helper.thread_utils import AsyncStream, async_run
from core import generation_utils
from . import shared_state as shared_state_module
from .lora import LoRAManager
from .queue_manager import queue_manager_instance

logger = logging.getLogger(__name__)

# This queue is the bridge from the agent back to the UI thread.
ui_update_queue = queue.Queue()

def worker_wrapper(output_queue_ref, **kwargs):
    """
    A wrapper that calls the real worker in a try-except block
    to catch and report any backend exceptions.
    """
    try:
        worker(output_queue_ref=output_queue_ref, **kwargs)
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"--- BACKEND WORKER CRASHED ---\n{tb_str}\n--------------------------", exc_info=True)
        output_queue_ref.push(('crash', tb_str))

class ProcessingAgent(threading.Thread):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProcessingAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        with self._lock:
            # Double-check inside the lock to ensure initialization happens only once.
            if hasattr(self, '_initialized') and self._initialized:
                return

            super().__init__(daemon=True)
            self.mailbox = queue.Queue()
            self.is_processing = False

            # On agent initialization (app startup), forcefully reset the queue's
            # processing and editing state. This prevents a stale state from a
            # previous session's `unload` event from causing a UI lockup on refresh.
            logger.info("ProcessingAgent initializing, resetting queue state to idle.")
            queue_manager_instance.set_processing(False)
            queue_manager_instance.clear_edit_mode()

            self.start()
            self._initialized = True

    def send(self, message):
        self.mailbox.put(message)

    def run(self):
        """The agent's main loop, waiting for messages."""
        while True:
            message = self.mailbox.get()
            if message.get("type") == "start":
                self._handle_start(message)
            elif message.get("type") == "stop_queue":
                self._handle_stop_queue()
            elif message.get("type") == "cancel_task":
                self._handle_cancel_task()
            elif message.get("type") == "pause":
                self._handle_pause()


    def _handle_start(self, message):
        if self.is_processing:
            return

        if not queue_manager_instance.has_pending_tasks():
            ui_update_queue.put(("info", "Queue is empty. Add tasks to process."))
            return

        self.is_processing = True
        queue_manager_instance.set_processing(True)
        ui_update_queue.put(("processing_started", None))
        shared_state_module.shared_state_instance.pause_request_flag.clear()
        shared_state_module.shared_state_instance.stop_requested_flag.clear()
        shared_state_module.shared_state_instance.interrupt_flag.clear()

        # Run the actual processing in a separate thread to not block the agent's mailbox
        processing_thread = threading.Thread(target=self._processing_loop, args=(message,))
        processing_thread.start()

    def _handle_stop_queue(self):
        """Handles a 'hard stop' request to terminate the entire queue."""
        if not self.is_processing:
            return
        shared_state_module.shared_state_instance.pause_request_flag.clear()
        ui_update_queue.put(("stopping_process", None))
        shared_state_module.shared_state_instance.stop_requested_flag.set()
        shared_state_module.shared_state_instance.interrupt_flag.set()
        logger.info("Stop Queue signal sent. Worker will be interrupted and the queue will halt.")

    def _handle_cancel_task(self):
        """Handles a 'soft stop' to cancel only the currently running task."""
        if not self.is_processing:
            return
        shared_state_module.shared_state_instance.interrupt_flag.set()
        logger.info("Cancel Task signal sent. Worker will stop, and the agent will proceed to the next task.")

    def _handle_pause(self):
        """Handles a request to pause the current task and save its state."""
        if not self.is_processing:
            return
        logger.info("Pause request received by agent. Setting flags.")
        shared_state_module.shared_state_instance.pause_request_flag.set()
        shared_state_module.shared_state_instance.interrupt_flag.set()
    def _processing_loop(self, start_message):
        lora_controls = start_message.get("lora_controls")

        lora_handler = LoRAManager()
        try:
            if lora_controls:
                lora_handler.apply_lora(*lora_controls)

            # The main processing loop. It will only terminate if a full stop is requested.
            while not shared_state_module.shared_state_instance.stop_requested_flag.is_set():
                # If a full stop hasn't been requested, we can clear the single-task interrupt flag
                # from a previous iteration. If a full stop IS requested, we must leave the
                # interrupt flag set for the worker to see it and halt. This prevents a race
                # condition where the flag is cleared before the worker can act on it.
                if not shared_state_module.shared_state_instance.stop_requested_flag.is_set():
                    shared_state_module.shared_state_instance.interrupt_flag.clear()

                if shared_state_module.shared_state_instance.stop_requested_flag.is_set() or shared_state_module.shared_state_instance.interrupt_flag.is_set():
                    break
                task = queue_manager_instance.get_and_start_next_task()

                if task is None:  # No more pending tasks
                    ui_update_queue.put(("info", "All tasks processed."))
                    break

                ui_update_queue.put(("task_starting", task))

                output_stream = AsyncStream()
                worker_args = {**task["params"], "task_id": task["id"], **shared_state_module.shared_state_instance.models}
                worker_args.pop('transformer', None)

                # The worker needs new arguments that the UI doesn't provide yet.
                # We add safe default values here to satisfy the full function signature.
                worker_args.setdefault('force_standard_fps', False) # This is a valid worker arg

                async_run(worker_wrapper, output_queue_ref=output_stream.output_queue, **worker_args)

                task_final_status = "error"
                final_output_path = None
                error_message = "Worker exited unexpectedly."

                while True:
                    # This is a blocking call. The agent will wait here until the worker
                    # sends a message. The `FIFOQueue` object from the helper library
                    # uses .next() and does not support timeouts.
                    flag, data = output_stream.output_queue.next()
                    ui_update_queue.put((flag, data))

                    if flag == "end":
                        _, success, final_path = data
                        task_final_status = "done" if success else "error"
                        final_output_path = final_path
                        break
                    elif flag == "crash":
                        task_final_status = "error"
                        error_message = "Worker process crashed."
                        break
                    elif flag == "aborted":
                        task_final_status = "aborted"
                        error_message = None
                        break
                    elif flag == "paused_with_state":
                        task_id, history_latents, preview_path = data
                        task_final_status = "paused"
                        error_message = None
                        final_output_path = preview_path # The preview generated before pausing

                        logger.info(f"Task {task_id} hypothetially paused with latent state. Saving resume file would happen here.")
                        break

                    elif flag == "file":
                        _, new_video_path, _ = data
                        final_output_path = new_video_path

                # If the task was aborted by the user, we want to reset its status to 'pending'
                # in the backend queue so it can be run again.
                final_status_for_queue = task_final_status
                if task_final_status == "aborted":
                    final_status_for_queue = "pending"
                    error_message = None

                queue_manager_instance.complete_task(
                    task_id=task["id"],
                    status=final_status_for_queue,
                    final_path=final_output_path,
                    error_msg=error_message
                )
                # The UI listener, however, still needs to know the original 'aborted' status
                # to perform the correct UI cleanup (e.g., clearing progress bars).
                ui_update_queue.put(("task_finished", {"id": task["id"], "status": task_final_status, "final_path": final_output_path}))

                if shared_state_module.shared_state_instance.stop_requested_flag.is_set() or shared_state_module.shared_state_instance.interrupt_flag.is_set():
                    ui_update_queue.put(("info", "Queue processing stopped by user."))
                    break
        finally:
            logger.info("Processing finished. Reverting all LoRAs to clean up.")
            lora_handler.revert_all_loras()
            logger.info("All LoRAs reverted. Processing agent is now idle.")
            self.is_processing = False
            queue_manager_instance.set_processing(False)
            shared_state_module.shared_state_instance.interrupt_flag.clear()
            shared_state_module.shared_state_instance.stop_requested_flag.clear()            
            shared_state_module.shared_state_instance.pause_request_flag.clear()
            logger.info("All state flags cleared.")
            ui_update_queue.put(("queue_finished", None))