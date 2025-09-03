# src/api/core_api.py
import threading
import queue
import logging
import numpy as np
from PIL import Image
from ui.queue_manager import queue_manager_instance
from ui.agents import ProcessingAgent
from ui import shared_state as shared_state_module # Keep for shared state access
# from ui import queue_helpers, metadata as metadata_manager
from ui.enums import UIMessage

logger = logging.getLogger(__name__)

class GoanAPI:
    """
    A UI-agnostic API for the goan application core. This class provides a stable,
    programmatic interface to all backend functionality, dealing only in primitive
    data types. It is completely decoupled from any specific UI framework.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GoanAPI, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        # These are the application's core, stateful components
        self.queue_manager = queue_manager_instance
        self.agent = ProcessingAgent()
        self.shared_state = shared_state_module.shared_state_instance
        self._initialized = True

    # --- Queue Management Methods ---

    def get_queue_state_snapshot(self) -> dict:
        """Returns a JSON-serializable snapshot of the current queue state."""
        state = self.queue_manager.get_state()
        # Convert numpy arrays in tasks to something serializable if needed,
        # for now, we assume this is for internal Python use.
        # For a web API, we'd convert images to base64/URLs here.
        return state

    def add_task(self, params: dict, image_np: np.ndarray) -> dict:
        """Adds a new task to the queue."""
        self.queue_manager.add_task(params, image_np)
        return self.get_queue_state_snapshot()

    def clear_pending_tasks(self) -> dict:
        """Clears all tasks with 'pending' status."""
        self.queue_manager.clear_pending_tasks()
        return self.get_queue_state_snapshot()

    # --- Processing Control Methods ---

    def start_processing(self, lora_controls: tuple) -> bool:
        """
        Starts the backend processing agent. Returns True if started, False otherwise.
        """
        if self.queue_manager.get_state().get("processing", False):
            logger.warning("API: Attempted to start processing, but it is already active.")
            return False

        self.shared_state.interrupt_flag.clear()
        self.shared_state.stop_requested_flag.clear()
        self.shared_state.preview_request_flag.clear()
        self.shared_state.pause_request_flag.clear()
        logger.info("API: State flags cleared for new queue run.")
        self.agent.send({
            "type": "start",
            "lora_controls": lora_controls
        })
        return True

    def stop_processing(self):
        """Requests a hard stop of the entire processing queue."""
        self.shared_state.stop_requested_flag.set()
        self.agent.send({"type": "stop_queue"})
        logger.info("API: Stop signal sent.")

    def cancel_current_task(self):
        """Requests a soft stop of only the currently running task."""
        self.agent.send({"type": "cancel_task"})
        logger.info("API: Cancel task signal sent.")

    def request_manual_preview(self):
        """Sets the flag to request a manual preview of the current segment."""
        if not self.queue_manager.get_state().get("processing", False):
            logger.warning("API: Cannot request preview when processing is not active.")
            return
        
        if self.shared_state.preview_request_flag.is_set():
            logger.info("API: Preview generation has already been requested.")
        else:
            logger.info("API: Manual preview requested. Setting flag.")
            self.shared_state.preview_request_flag.set()

    # --- Metadata and Image Handling ---
    
    def extract_metadata_from_image(self, pil_image: Image.Image) -> dict:
        """Extracts 'goan' parameter metadata from a PIL image."""
        return metadata_manager.extract_metadata_from_pil_image(pil_image)

    def get_typed_params_from_metadata(self, metadata: dict) -> dict:
        """
        Converts raw metadata strings into a dictionary of properly typed
        creative parameters.
        """
        return metadata_manager.ui_load_params_from_image_metadata(metadata)

    def prepare_image_with_metadata(self, pil_image: Image.Image, params_from_ui: dict, lora_info: dict) -> bytes:
        """
        Injects metadata into a PIL image and returns it as PNG bytes.
        """
        params_dict = params_from_ui.copy()
        if lora_info.get("name") and lora_info["name"] != "None":
            params_dict["loras"] = [lora_info]
        
        pnginfo_obj = metadata_manager.create_pnginfo_obj(params_dict)
        
        with queue_helpers.io.BytesIO() as buf:
            pil_image.save(buf, "PNG", pnginfo=pnginfo_obj)
            return buf.getvalue()

# Singleton instance for the application to use
goan_api_instance = GoanAPI()
