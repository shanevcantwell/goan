# TODO: Task Checkpointing & Resumption Feature

---
# Design Doc: Multi-User Architecture and Stateless I/O

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-06
**Status:** Design Complete, Implementation Deferred Post-Alpha

This document outlines the design for a crash-proof task resumption feature. The goal is to allow users to recover from application crashes or intentional pauses without losing significant progress.

---

## 1. Core Mechanism: Transactional Checkpointing

To prevent corrupted state files during a crash, the system will use a "write-then-rename" atomic operation.

1.  **Write to Temp:** After each successful video segment, the worker will save the complete resume state (the latest `history_latents` tensor, the current segment number, and all creative parameters) to a temporary file (e.g., `task_123.tmp`).
2.  **Atomic Rename:** Once the write is complete and flushed to disk, the worker will perform an atomic `os.replace()` to rename the temporary file to the final checkpoint file (e.g., `task_123.goan_resume`).

This ensures that the `.goan_resume` file is never in a partially-written state.

---

## 2. Implementation - Backend

### `src/core/checkpointing.py` (New File)

A new module will encapsulate all logic for saving and loading checkpoints transactionally.

```python
import os
import torch
import json
import zipfile
import tempfile
import logging

logger = logging.getLogger(__name__)

RESUME_STATE_FILENAME = "resume_state.json"
LATENTS_FILENAME = "history_latents.pt"
SOURCE_IMAGE_FILENAME = "source_image.png"

def save_checkpoint(job_id, segment_number, history_latents, source_image_np, params_to_save, output_folder):
    """Saves the current generation state to a transactional checkpoint file."""
    checkpoint_filename = f"{job_id}_seg_{segment_number}.goan_resume"
    final_checkpoint_path = os.path.join(output_folder, checkpoint_filename)
    
    temp_fd, temp_path = tempfile.mkstemp(dir=output_folder, suffix=".tmp")
    os.close(temp_fd)

    try:
        resume_state = {
            "next_segment_to_process": segment_number + 1,
            "params": params_to_save
        }

        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(RESUME_STATE_FILENAME, json.dumps(resume_state, indent=4))
            
            with zf.open(LATENTS_FILENAME, 'w') as f:
                torch.save(history_latents.cpu(), f)

            img = Image.fromarray(source_image_np)
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                zf.writestr(SOURCE_IMAGE_FILENAME, buf.getvalue())

        os.replace(temp_path, final_checkpoint_path)
        logger.info(f"Checkpoint for job '{job_id}' saved successfully.")
        return final_checkpoint_path
    except Exception as e:
        logger.error(f"Failed to save checkpoint for job '{job_id}': {e}", exc_info=True)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def load_checkpoint(checkpoint_path):
    """Loads the generation state from a checkpoint file."""
    try:
        with zipfile.ZipFile(checkpoint_path, 'r') as zf:
            with zf.open(RESUME_STATE_FILENAME, 'r') as f:
                resume_state = json.load(f)
            
            with zf.open(LATENTS_FILENAME, 'r') as f:
                history_latents = torch.load(f, map_location="cpu")

            with zf.open(SOURCE_IMAGE_FILENAME, 'r') as img_file:
                source_image_pil = Image.open(io.BytesIO(img_file.read())).convert("RGBA")
                source_image_np = np.array(source_image_pil)

        return resume_state, history_latents, source_image_np
    except Exception as e:
        logger.error(f"Failed to load checkpoint from '{checkpoint_path}': {e}", exc_info=True)
        return None, None, None

def delete_checkpoint(checkpoint_path):
    """Deletes a checkpoint file upon successful completion of a task."""
    if checkpoint_path and os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
            logger.info(f"Cleaned up checkpoint file: {checkpoint_path}")
        except OSError as e:
            logger.warning(f"Failed to delete checkpoint file '{checkpoint_path}': {e}")
```

### `src/core/generation_core.py` (Modifications)

The `worker` will be modified to accept a `resume_latent_path`. If provided, it will call `checkpointing.load_checkpoint` to initialize its state (`history_latents`, `start_segment`) and then begin the generation loop from the correct segment. After each successful segment, it will call `checkpointing.save_checkpoint`.

---

## 3. Implementation - Frontend

### `src/ui/queue.py` (Modifications)

A new handler, `add_resumable_task_from_zip`, will be created. When a `.goan_resume` file is dropped, this handler will:
1. Call `checkpointing.load_checkpoint` to extract the parameters and original source image.
2. Add a new task to the queue with these parameters.
3. Critically, it will add a `resume_latent_path` key to the task's parameters, pointing to the `.goan_resume` file itself. This tells the worker where to load the latent history from.

---

## 4. Relationship to UI Session Restore

It is important to distinguish between **Task Resumption** (the focus of this document) and **UI Session Restore**.

*   **Task Resumption**: Recovers the state of a *backend worker process* that was actively generating a video. It involves saving and loading complex data like PyTorch latent tensors.

*   **UI Session Restore**: Recovers the state of the *frontend UI controls and task queue* after an accidental browser refresh, closure, or navigation away from the page (the "backspace-key-disaster"). This is the primary defense against losing your configured "recipes" and queue setup.

The application already has a robust mechanism for UI Session Restore, which complements the task checkpointing system:

1.  **On Exit/Unload**: The Gradio `unload` event triggers two key functions:
    *   `workspace.save_ui_and_image_for_refresh`: Saves all current UI control values and the input image to temporary files (`goan_unload_save.json`, `goan_refresh_image.png`).
    *   `queue.autosave_queue_on_exit_action`: Saves the entire task queue, including all parameters and task-specific images, to a temporary zip file.

2.  **On Load**: When the application is started or the page is reloaded, the `block.load` event in `switchboard_startup.py` orchestrates the loading of these temporary files, restoring the UI and queue to their last known state.

This existing system ensures that even if a user accidentally navigates away, their entire workspace configuration is preserved and automatically restored, preventing the loss of work before a generation has even started. The plan to move to *periodic* autosaving (as noted in the main `TODO.md`) will make this defense even stronger.

### `src/ui/workspace.py` & Switchboards (Modifications)

The main file drop handler (`handle_file_drop`) will be updated to detect `.goan_resume` files and delegate them to the new `add_resumable_task_from_zip` handler in `queue.py`.

---

### Notes on flow implementation (originally in DEVELOPERS_GUIDE.md): Pausing and Resuming a Task

This flow is essential for the checkpointing feature.

1.  **User Action**: The user clicks the "Pause" button while a task is running.
2.  **Signal Path**: The UI listener sends a `{"type": "pause"}` message to the `ProcessingAgent`, which sets the `pause_request_flag`.
3.  **Worker Checkpoint**: The `worker`, at a safe point (e.g., between generation segments), checks `pause_request_flag.is_set()`.
4.  **State Bundling**: Upon detecting the flag, the worker bundles its critical state (e.g., current latents, segment index, RNG state) into a `state_data` dictionary.
5.  **Signal Pause**: The worker pushes a `('paused_with_state', state_data)` message to the `ProcessingAgent` and enters a waiting state.
6.  **Agent & UI Update**: The agent receives the message, forwards a `task_paused` event to the `ui_update_queue`, and stores the `state_data` associated with the task. The UI updates to show a "Paused" status.
7.  **User Resumes**: The "Process Queue" button will have changed to a "Resume" button. The user clicks it.
8.  **Resume Signal**: The UI listener sends a `{"type": "resume"}` message to the `ProcessingAgent`.
9.  **Agent Orchestration**: The agent retrieves the stored `state_data` for the paused task and signals the waiting `worker` thread to continue, passing the `state_data` back to it.
10. **Worker Resumes**: The `worker` receives the signal, unpacks the `state_data` to restore its state, and resumes the generation process exactly where it left off.
