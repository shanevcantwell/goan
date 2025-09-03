# main_api.py
import os
import sys
import logging
import logging.handlers
import warnings
import asyncio
import uvicorn
from fastapi import FastAPI, UploadFile, File, Body, Request
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image
import numpy as np
import io

# Setup sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Suppress warnings
warnings.filterwarnings("ignore", message="The video decoding and encoding capabilities of torchvision are deprecated")

# Local Application Imports
from core import args as args_manager
from core import model_loader
from api.core_api import goan_api_instance
from api.pydantic_models import QueueState, TaskParams, LoraControls
from api.sse_manager import sse_manager
from ui import shared_state as shared_state_module

# --- Logging Setup (copied from goan.py) ---
def setup_logging(debug_mode=False):
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_filepath = os.path.join(log_dir, 'goan_api.log')
    file_log_level = logging.DEBUG if debug_mode else logging.INFO
    console_log_level = logging.INFO if debug_mode else logging.WARNING
    root_logger = logging.getLogger()
    root_logger.setLevel(min(file_log_level, console_log_level))
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.handlers.TimedRotatingFileHandler(log_filepath, when='midnight', interval=1, backupCount=7, encoding='utf-8')
    file_handler.setLevel(file_log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(console_log_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

# --- FastAPI App Initialization ---
app = FastAPI(title="Goan API", version="1.0")
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Load models on application startup."""
    logger.info("Starting up and loading models...")
    os.environ['HF_HOME'] = os.path.abspath(os.path.realpath('./hf_download'))
    model_loader.load_and_configure_models()
    logger.info("Models loaded successfully.")

# --- API Endpoints ---

@app.get("/api/queue", response_model=QueueState)
async def get_queue_state():
    """Returns the current state of the processing queue."""
    state = goan_api_instance.get_queue_state_snapshot()
    # Pydantic will automatically handle the conversion of the dict to the response model
    return state

@app.post("/api/tasks")
async def add_task_to_queue(
    params: TaskParams = Body(...),
    image: UploadFile = File(...)
):
    """Adds a new task to the queue with an uploaded image."""
    try:
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        image_np = np.array(pil_image)
        
        # Convert Pydantic model to a dictionary for the backend
        worker_params = {shared_state_module.UI_TO_WORKER_PARAM_MAP[K(k)]: v for k, v in params.dict().items()}
        
        goan_api_instance.add_task(worker_params, image_np)
        return JSONResponse({"message": "Task added successfully."}, status_code=201)
    except Exception as e:
        logger.error(f"Error adding task: {e}", exc_info=True)
        return JSONResponse({"error": "Failed to add task."}, status_code=500)

@app.post("/api/processing/start")
async def start_processing(lora_controls: LoraControls):
    """Starts processing the queue."""
    # Convert LoraControls to the tuple format the agent expects
    lora_tuple = (lora_controls.lora_name, lora_controls.lora_weight, lora_controls.lora_targets)
    success = goan_api_instance.start_processing(lora_tuple)
    if success:
        return {"message": "Processing started."}
    return JSONResponse({"error": "Processing is already active or queue is empty."}, status_code=409)

@app.post("/api/processing/stop")
async def stop_processing():
    """Stops the processing queue."""
    goan_api_instance.stop_processing()
    return {"message": "Stop signal sent."}

@app.get("/api/stream")
async def stream_events(request: Request):
    """Endpoint for Server-Sent Events to stream progress updates."""
    client_queue = asyncio.Queue()
    await sse_manager.connect(client_queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream.")
                    break
                
                message = await client_queue.get()
                yield f"data: {message}\n\n"
        finally:
            await sse_manager.disconnect(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Main Execution ---
if __name__ == "__main__":
    args = args_manager.parse_args()
    setup_logging(debug_mode=args.debug)
    
    # Default port if not provided
    port = args.port if args.port else 8000
    
    logger.info(f"Starting Goan API server on {args.server}:{port}")
    uvicorn.run(app, host=args.server, port=port)
