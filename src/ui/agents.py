# ui/agents.py
import threading
import queue
import logging
import traceback
import numpy as np
import asyncio

from core.generation_core import worker
from diffusers_helper.thread_utils import AsyncStream, async_run
from . import shared_state as shared_state_module
from .enums import UIMessage
from .lora import lora_key_mapper as LoRAManager
from .queue_manager import queue_manager_instance
from api.sse_manager import sse_manager # <-- IMPORT THE NEW MANAGER

logger = logging.getLogger(__name__)

# The ui_update_queue is now obsolete and can be removed.
# We keep the agent's mailbox for commands from the API.

def broadcast_sync(flag, data):
    """Helper to run the async broadcast from a synchronous thread."""
    try:
        # Get or create an event loop for the current thread
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(sse_manager.broadcast(flag, data))

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
        output_queue_ref.push((UIMessage.CRASH, tb_str))

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
            if hasattr(self, '_initialized') and self._initialized:
                return
            super().__init__(daemon=True)
            self.mailbox = queue.Queue()
            self.is_processing = False
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
        if self.is_processing: return
        if not queue_manager_instance.has_pending_tasks():
            broadcast_sync(UIMessage.INFO, "Queue is empty. Add tasks to process.")
            return

        self.is_processing = True
        queue_manager_instance.set_processing(True)
        broadcast_sync(UIMessage.PROCESSING_STARTED, None)
        shared_state_module.shared_state_instance.pause_request_flag.clear()
        shared_state_module.shared_state_instance.stop_requested_flag.clear()
        shared_state_module.shared_state_instance.interrupt_flag.clear()
        processing_thread = threading.Thread(target=self._processing_loop, args=(message,))
        processing_thread.start()

    def _handle_stop_queue(self):
        if not self.is_processing: return
        shared_state_module.shared_state_instance.pause_request_flag.clear()
        broadcast_sync(UIMessage.STOPPING_PROCESS, None)
        shared_state_module.shared_state_instance.stop_requested_flag.set()
        shared_state_module.shared_state_instance.interrupt_flag.set()
        logger.info("Stop Queue signal sent.")

    def _handle_cancel_task(self):
        if not self.is_processing: return
        shared_state_module.shared_state_instance.interrupt_flag.set()
        logger.info("Cancel Task signal sent.")

    def _handle_pause(self):
        if not self.is_processing: return
        logger.info("Pause request received by agent. Setting flags.")
        shared_state_module.shared_state_instance.pause_request_flag.set()
        shared_state_module.shared_state_instance.interrupt_flag.set()

    def _processing_loop(self, start_message):
        lora_controls = start_message.get("lora_controls")
        lora_handler = LoRAManager()
        try:
            if lora_controls:
                lora_handler.apply_lora(*lora_controls)

            while not shared_state_module.shared_state_instance.stop_requested_flag.is_set():
                if not shared_state_module.shared_state_instance.stop_requested_flag.is_set():
                    shared_state_module.shared_state_instance.interrupt_flag.clear()
                if shared_state_module.shared_state_instance.stop_requested_flag.is_set(): break
                
                task = queue_manager_instance.get_and_start_next_task()
                if task is None:
                    broadcast_sync(UIMessage.INFO, "All tasks processed.")
                    break

                broadcast_sync(UIMessage.TASK_STARTING, task)
                output_stream = AsyncStream()
                worker_args = {**task["params"], "task_id": task["id"], **shared_state_module.shared_state_instance.models}
                worker_args.pop('transformer', None)
                worker_args.setdefault('force_standard_fps', False)
                async_run(worker_wrapper, output_queue_ref=output_stream.output_queue, **worker_args)

                task_final_status = "error"
                final_output_path = None
                error_message = "Worker exited unexpectedly."

                while True:
                    flag, data = output_stream.output_queue.next()
                    
                    # Broadcast all messages to clients
                    broadcast_sync(flag, data)

                    if flag in [UIMessage.END, UIMessage.CRASH, UIMessage.ERROR, UIMessage.ABORTED, UIMessage.PAUSED_WITH_STATE]:
                        if flag == UIMessage.END:
                            success = data.get('success', False)
                            task_final_status = "done" if success else "error"
                            final_output_path = data.get('final_path')
                        elif flag in [UIMessage.CRASH, UIMessage.ERROR]:
                            task_final_status = "error"
                            error_message = data.get('message', "Worker crashed.") if isinstance(data, dict) else str(data)
                        elif flag == UIMessage.ABORTED:
                            task_final_status = "aborted"
                            error_message = None
                        elif flag == UIMessage.PAUSED_WITH_STATE:
                            task_final_status = "paused"
                            error_message = None
                            final_output_path = data.get('preview_path')
                        break

                final_status_for_queue = "pending" if task_final_status == "aborted" else task_final_status
                queue_manager_instance.complete_task(
                    task_id=task["id"], status=final_status_for_queue,
                    final_path=final_output_path, error_msg=error_message
                )
                broadcast_sync(UIMessage.TASK_FINISHED, {"id": task["id"], "status": task_final_status, "final_path": final_output_path})

                if shared_state_module.shared_state_instance.stop_requested_flag.is_set():
                    broadcast_sync(UIMessage.INFO, "Queue processing stopped by user.")
                    break
        finally:
            logger.info("Processing finished. Reverting all LoRAs.")
            lora_handler.revert_all_loras()
            self.is_processing = False
            queue_manager_instance.set_processing(False)
            shared_state_module.shared_state_instance.interrupt_flag.clear()
            shared_state_module.shared_state_instance.stop_requested_flag.clear()
            shared_state_module.shared_state_instance.pause_request_flag.clear()
            logger.info("All state flags cleared.")
            broadcast_sync(UIMessage.QUEUE_FINISHED, None)
