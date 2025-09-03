# api/pydantic_models.py
from pydantic import BaseModel, Field
from typing import List, Optional

from ui.enums import TaskStatus

# Re-export the enum for use in API schemas
TaskStatusEnum = TaskStatus

class TaskParams(BaseModel):
    """Pydantic model for the creative and environment parameters of a task."""
    prompt: str
    negative_prompt: str = ""
    video_length: float = Field(default=5.0, gt=0)
    seed: int = -1
    preview_frequency: int = Field(default=10, ge=0)
    preview_specified_segments: str = ""
    fps: int = Field(default=30, gt=0)
    distilled_cfg_start: float = 10.0
    variable_cfg_shape: str = "Off"
    distilled_cfg_end: float = 10.0
    roll_off_start: float = 75.0
    roll_off_factor: float = 1.0
    steps: int = Field(default=25, gt=0)
    real_cfg: float = 1.0
    guidance_rescale: float = 0.0
    use_teacache: bool = True
    use_fp32_transformer_output: bool = False
    gpu_memory_preservation: float = 6.0
    mp4_crf: int = Field(default=18, ge=0, le=51)
    output_folder: str
    latent_window_size: int = 9

class Task(BaseModel):
    """Pydantic model representing a single task in the queue."""
    id: int
    status: TaskStatusEnum
    params: dict # For simplicity, we'll keep params generic here
    final_output_filename: Optional[str] = None
    error_message: Optional[str] = None

class QueueState(BaseModel):
    """Pydantic model for the entire queue state."""
    queue: List[Task]
    next_id: int
    processing: bool
    editing_task_id: Optional[int] = None

class LoraControls(BaseModel):
    """Pydantic model for LoRA settings for a processing run."""
    lora_name: Optional[str] = None
    lora_weight: float = 1.0
    lora_targets: List[str] = []
