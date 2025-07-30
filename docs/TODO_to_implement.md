# TODO & Loose Ends

This document tracks features that are partially implemented or planned for the near future, based on the current state of the codebase.

---

### 1. Synchronize Video Player Components

*   **Issue**: The UI now has two video players: `LAST_FINISHED_VIDEO` (in the two-column layout) and `LAST_FINISHED_VIDEO_FULL_WIDTH` (in the full-width layout). Currently, only the first one is updated when a video generation completes.
*   **Task**: Modify the `queue_processing` generator to yield updates for **both** video components simultaneously whenever a new video file is produced. This will ensure the video is visible regardless of which layout the user has selected.

---

### 2. Implement "Cancel Edit" Functionality

*   **Issue**: The "Cancel Edit" button is present but commented out in `src/ui/layout.py`, and its event wiring is commented out in `src/ui/switchboard_queue.py`. The backend logic (`queue.cancel_edit_mode_action`) already exists.
*   **Task**: Uncomment the `CANCEL_EDIT_TASK_BUTTON` in the layout and its corresponding event wiring in the switchboard to make this feature fully functional.

---
### 5. Fix Bug in LoRA Static Merging

*   **Issue**: The `_merge_model_statically` function in `src/ui/lora.py` has a bug that prevents it from working correctly. It attempts to use an undefined variable `rank` before it is calculated, and it references an undefined dictionary `lora_tensors` instead of the correct `translated_lora_tensors`.
*   **Task**: Correct the variable names and the order of operations in the function. The `rank` should be inferred from the shape of the `down_w` tensor *before* it is used to calculate the `alpha` and `scale` values. The `lora_tensors` variable should be changed to `translated_lora_tensors` to match the function's scope.

---