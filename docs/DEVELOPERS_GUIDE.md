# Developer's Guide to Extending 'goan'

## 1. Introduction & Core Philosophy

This document provides a technical overview of the `goan` application architecture. It is intended for developers looking to understand, maintain, or extend the codebase.

The application is built on four core principles:

1.  **Separation of Concerns**: The user interface (UI) is strictly separated from the backend generation engine. The UI's role is to capture user intent and display results, while the backend's role is to execute generation tasks.
2.  **Centralized State Management**:
    *   **`SharedState`**: A singleton holding global, thread-safe state like threading events (`interrupt_flag`), loaded PyTorch models, and system info.
    *   **`QueueManager`**: A thread-safe singleton that exclusively manages the task queue's data and state (adding, removing, reordering, etc.).
3.  **Agent-Based Backend Orchestration**: A central `ProcessingAgent` singleton manages the entire lifecycle of the backend `worker` thread. This decouples the long-running generation process from the UI event loop.
4.  **Asynchronous UI Updates**: All communication from the backend worker to the UI is funneled through the `ProcessingAgent` to a single, global `ui_update_queue`. A dedicated UI listener (`process_task_queue_and_listen`) consumes this queue and yields updates to Gradio, preventing race conditions and simplifying state management.

---

### State Management at a Glance

| Component | Responsibility | Key State Attributes |
| :--- | :--- | :--- |
| **`SharedState`** | Holds global, thread-safe application state and threading events. | `interrupt_flag`, `stop_requested_flag`, `manual_preview_request_flag`, `pause_request_flag`, `models` (dict), `system_info` (dict) |
| **`QueueManager`** | Manages all operations on the task queue data structure. Responsible for orchestrating the saving and loading of the queue to/from disk for session persistence. | `queue` (list), `processing` (bool), `next_task_id` (int) |

---

## 2. Core Architecture Overview

The application can be understood as three main layers:

*   **Frontend (Gradio View Layer)**: Defined in `ui/layout.py`. This layer is responsible only for creating and arranging the Gradio components. It is a "dumb" layer with no event logic.

*   **Backend (Worker Engine)**: The `worker` function in `core/generation_core.py` is the heart of the generation process. It runs in a separate thread and is completely decoupled from Gradio. It accepts a dictionary of parameters and communicates its progress back to the `ProcessingAgent` via a dedicated message queue.

*   **UI Logic (The "Glue" Layer)**: This layer bridges the gap between the Frontend and the Backend and resides primarily in the `src/ui/` directory.
    *   **`ui/agents.py`**: Defines the `ProcessingAgent`, a singleton that orchestrates the backend. It receives commands (e.g., "start", "stop") via its `mailbox` and launches the `worker` in a separate thread. It is the sole consumer of the worker's output stream.
    *   **`ui/queue_processing.py`**: Contains the `process_task_queue_and_listen` generator. This function is the UI's main entry point for starting processing. It sends the "start" command to the agent and then enters a loop, consuming messages from the global `ui_update_queue` and `yield`ing updates to Gradio.
    *   **`ui/queue_manager.py`**: The thread-safe singleton for all queue data operations.
    *   **Handler Modules (`ui/event_handlers.py`, `ui/queue.py`, etc.)**: These modules contain handler functions for synchronous UI events (e.g., adding a task, clearing an image). Following the **"Handler-Returns-Dict"** pattern, these functions perform business logic and **must return a dictionary** where keys are `ComponentKey` enums and values are `gr.update()` objects. They are decoupled from the UI layout.
    *   **`switchboard_*.py` files**: These modules are the single source of truth for wiring UI component events (e.g., `.click()`, `.upload()`) to handlers. They define the list of UI components an event should affect and use a helper function (`apply_updates`) in a `.then()` block to map the dictionary from the handler to the UI outputs.
---

### Agent & Worker Communication

Communication between the UI, the agent, and the worker is handled via message passing through queues and events.

| Sender | Receiver | Message / Event | Purpose |
| :--- | :--- | :--- | :--- |
| **UI Listener** | `ProcessingAgent` | `{"type": "start"}` | Start processing the task queue. |
| **UI Listener** | `ProcessingAgent` | `{"type": "stop_queue"}` | Request a hard stop of the entire queue. |
| **UI Listener** | `ProcessingAgent` | `{"type": "cancel_task"}` | Request a soft stop of only the current task. |
| **UI Listener** | `ProcessingAgent` | `{"type": "pause"}` | Request a graceful pause of the current task. |
| **`worker`** | `ProcessingAgent` | `('progress', data)` | Send real-time progress updates (image, text, progress bar). |
| **`worker`** | `ProcessingAgent` | `('file', data)` | Notify that a preview or final video file has been saved. |
| **`worker`** | `ProcessingAgent` | `('end', data)` | Signal that the task has completed successfully. |
| **`worker`** | `ProcessingAgent` | `('error', data)` | Signal that a fatal error occurred. |
| **`worker`** | `ProcessingAgent` | `('paused_with_state', data)` | Signal a successful pause and provide resume data. |
| **`ProcessingAgent`** | **`worker`** | `interrupt_flag.set()` | Signal the worker to perform an immediate, hard stop. |
| **`ProcessingAgent`** | **`worker`** | `pause_request_flag.set()` | Signal the worker to perform a graceful pause. |

---

## 3. Key Process Flows (Summarized)

*   **Starting a Task**: The user clicks "Process Queue". The UI listener (`queue_processing`) sends a "start" message to the `ProcessingAgent`. The agent launches the `worker` in a new thread. The worker pushes progress updates back to the agent, which forwards them to a global `ui_update_queue`. The UI listener consumes this queue and yields updates to Gradio.

*   **Stopping a Task**: The user clicks a stop button. A handler sends a "stop" or "cancel" message to the `ProcessingAgent`, which sets the `interrupt_flag`. The `worker` frequently checks this flag, raises an `InterruptedError` upon detection, and exits gracefully.

*   **Manual Preview**: The user clicks "Create Preview". A handler sets the `manual_preview_request_flag`. The `worker` checks this flag at the start of each segment, generates a preview if set, and then clears the flag.

---

## 4. UI State Logic: The Button State Machine

The interactivity of the main control buttons is managed by a single function, `update_button_states` in `event_handlers.py`. It acts as a state machine, deriving the application's current state and applying a set of rules to determine which buttons should be enabled or disabled.

| Application State | `Process Queue` Button | `Add Task` Button | `Create Preview` Button | Other Buttons |
| :--- | :--- | :--- | :--- | :--- |
| **Stopping** | `Stopping...` (enabled, stop variant) | Enabled | Disabled | `Clear/Download Image` enabled. `Save/Clear Queue` disabled. |
| **Processing** | `Stop Processing` (enabled, stop variant) | Enabled (if image present) | Enabled (as a toggle) | `Save/Clear Queue` and `Clear/Download Image` enabled based on context. |
| **Idle** | Enabled (if queue has tasks) | Enabled (if image present) | Disabled | `Save/Clear Queue` and `Clear/Download Image` enabled based on context. |

---

## 5. Notable Implementations

### Legacy GPU Support (Compute Capability < 8.0)

The application provides out-of-the-box support for older NVIDIA GPUs (Turing architecture, SM7.5) that lack `bfloat16` support. This is handled through a series of automated steps:

1.  **Detection**: On startup, `core/model_loader.py` checks the GPU's compute capability. If it's less than 8.0, it sets a global `is_legacy_gpu` flag in `shared_state_instance`.
2.  **Model Loading**: When the `transformer` is loaded, this flag forces its data type to `torch.float32` instead of the default `torch.bfloat16`, preventing data type errors on older hardware.
3.  **Inference**: The `worker` in `core/generation_core.py` also checks this flag and forces the `use_fp32_transformer_output` setting to `True`, ensuring stable inference. The corresponding UI checkbox is automatically hidden to prevent user confusion.

This approach, based on work by `@freely-boss`, ensures maximum compatibility without requiring any user intervention.

### PNG Metadata for "Recipes"

The application allows users to save and load their exact generation settings by embedding them in the input image's metadata, a feature common in other creative AI tools.

*   **Saving a Recipe**:
    1.  When the user clicks "Download Image", an event handler in `ui/workspace.py` is triggered.
    2.  The `prepare_image_for_download` function gathers all relevant parameters from the UI controls into a dictionary.
    3.  The dictionary is serialized into a JSON string and saved into the PNG's metadata using the `Pillow` library.

*   **Loading a Recipe**:
    1.  The main image input component is wired with an `.upload()` event handler in `ui/switchboard_image.py`.
    2.  When a user drops a PNG file, the `handle_image_upload` function (in `ui/event_handlers.py`) is executed.
    3.  It uses `Pillow` to open the image and inspects its metadata for the `goan_params` key.
    4.  If found, the parameters are extracted, and a confirmation modal is shown to the user.
    5.  If the user agrees, the `handle_confirm_metadata` function is called, which returns a dictionary of `gr.update()` objects to populate the UI.

*   **Metadata Schema Example**:
    To make recipes fully portable, LoRA settings are also saved. The parameters are stored as a JSON object under the `goan_params` key inside the PNG's metadata. Here is an example of the structure:

    ```json
    "parameters": {
        "prompt": "a beautiful landscape",
        "seed": 12345,
        "loras": [
            {
                "name": "MyCharacterV2.safetensors",
                "weight": 0.75,
                "targets": ["transformer", "text_encoder"]
            }
        ]
    }
    ```
---

### LoRA Application and Reversion (Single LoRA)

The current implementation supports applying a single LoRA per task queue run. The system is designed to be robust, handling the entire lifecycle of applying and reverting LoRA weights without leaving the models in a modified state. The core logic resides in the `LoRAManager` class in `src/ui/lora.py`.

*   **Workflow**: The user can upload a `.safetensors` file via the "Upload LoRA" button in the "LoRA" settings panel. The file is copied to a local `./loras` cache directory. The UI then displays controls to set the weight and target models for this single LoRA, which will be applied to all tasks in the next queue run. All multi-LoRA or URL-based features are deferred.

*   **Lifecycle**: The `ProcessingAgent` creates a `LoRAManager` instance at the start of a queue run. It applies all configured LoRAs and ensures `revert_all_loras` is called in a `finally` block, guaranteeing that models are cleaned up even if an error occurs.

*   **Static Merging**: `goan` uses a static merging strategy. Instead of injecting adapter layers, it directly modifies the weights of the target model layers in memory.
    *   Before a weight is modified, its original state is cloned and stored in the `_original_params` dictionary.
    *   The LoRA's `down` and `up` weights are used to calculate a `delta_w` tensor, which is then added to the original weight.

*   **Key Name Translation & Compatibility**:
    *   **Automatic Translation**: A key feature is the `_convert_hunyuan_keys_to_framepack` function. Many "wild" LoRAs are trained using different conventions (e.g., `kohya-ss`). This function acts as a translator, intelligently renaming layers from common formats to match the specific architecture of the FramePack models. This includes complex operations like splitting a single `QKV` weight tensor from a LoRA into the separate `Q`, `K`, and `V` weights required by the model.
    *   **Model Mismatch**: While the translator improves compatibility, it's important to note that FramePack is a fine-tuned version of the base Hunyuan model. Applying a LoRA trained on the base Hunyuan model may produce unpredictable or unintended effects.
    *   **Unknown Keys**: The key translator is based on common LoRA formats. It is possible to encounter a LoRA with a novel key naming scheme that the translator does not recognize. In such cases, the LoRA may fail to apply to any layers.

*   **UI Feedback**: To address the inconsistent nature of wild LoRAs, the `apply_lora` function provides immediate feedback to the user via a `gr.Info` or `gr.Warning` popup, reporting exactly how many layers were successfully merged. This instantly tells the user if a given LoRA is compatible with the selected model targets.

    #### How to Add a New LoRA Key Mapping

    If you encounter a LoRA that fails to map correctly, you may need to add a new translation rule. The first step is to diagnose the mismatch using the provided inspection tool:

    ```bash
    python src/lora/lora_key_inspector.py /path/to/your/lora.safetensors
    ```

    This script will print a report showing which keys from the LoRA file were successfully mapped and, more importantly, which were not. You can use the list of unmapped keys to determine the necessary translations.

    All translation logic resides in `src/lora/lora_key_mapper.py`. There are two primary places to add rules:

    1.  **For Simple Prefix Changes**: If a LoRA uses a different top-level prefix (e.g., `lora_sdxl_...` instead of `lora_unet_...`), add a new entry to the `KEY_PREFIX_TRANSLATION_RULES` dictionary. This is for simple, global replacements.

        ```python
        # In: src/lora/lora_key_mapper.py
        KEY_PREFIX_TRANSLATION_RULES = {
            "lora_unet_": "transformer.",
            # ... other rules ...
            "new_lora_prefix_": "transformer.", # Add your new rule here
        }
        ```

    2.  **For Internal Layer Name Changes**: If the internal layer names are different (e.g., the LoRA uses `attention_block` while the model expects `attn`), you need to add a rule to the `hunyuan_key_replacements` dictionary inside the `_convert_hunyuan_keys_to_framepack` function. The file contains a commented-out dummy example to use as a template.

        ```python
        # In: src/lora/lora_key_mapper.py, inside _convert_hunyuan_keys_to_framepack()
        hunyuan_key_replacements = {
            "double_blocks": "transformer_blocks",
            # ... other rules ...
            # --- Dummy Example for adding a new rule ---
            # "name_in_lora_file": "name_in_framepack_model",
        }
        ```

    By adding rules to these dictionaries, you can extend the application's compatibility with a wider range of community-provided LoRAs.

*   **Device-Aware Reversion**: The `revert_all_loras` function is carefully designed to prevent device mismatch errors. When restoring a backed-up weight from CPU memory to a model that is currently on the GPU, it explicitly calls `.to(model_device)` on the parameter before assigning it. This prevents the common `RuntimeError: Expected all tensors to be on the same device...` that can occur in complex, memory-managed pipelines.

---

## 6. Module Contracts (File-by-File)

### `src/core/` - The Backend Engine

* **`generation_core.py`**: **Contract**: Defines the `worker` function. It must be self-contained and must not import `gradio`. It communicates *only* through the `output_queue_ref` passed to it.
* **`model_loader.py`**: **Contract**: Responsible for loading all PyTorch models, detecting hardware capabilities (`is_legacy_gpu`), setting model `dtype` appropriately, and storing references in `shared_state_instance`. Manages lazy loading for the transformer and installs `DynamicSwapInstaller` in low-VRAM mode.
* **`generation_utils.py`**: **Contract**: Contains helper functions for the `worker`, such as `handle_segment_saving`.

### `src/ui/` - The Frontend and Glue Logic

* **`enums.py`**: **Contract**: Defines the `ComponentKey` `StrEnum`. All new UI components **must** have a key added here.
* **`shared_state.py`**: **Contract**: Defines the `SharedState` singleton, global threading primitives, parameter maps, and the `IS_LEGACY_GPU_KEY` constant.
* **`layout.py`**: **Contract**: Defines the entire Gradio UI component tree. Contains no event handling logic.
* **`switchboard_*.py` files**: **Contract**: Define the `outputs` list for each event and wire UI components to their corresponding handler functions.
* **`agents.py`**: **Contract**: Defines the `ProcessingAgent`. Its sole responsibility is to manage the lifecycle of the `worker` thread and bridge communication between the worker and the UI listener.
* **`queue_processing.py`**: **Contract**: Contains the primary UI listener generator that starts processing and consumes the `ui_update_queue` to update the UI asynchronously.
* **`queue_manager.py`**: **Contract**: Implements the `QueueManager` singleton. This is the **only** class that should directly modify the queue's internal state (`self.state["queue"]`).
* **`queue.py`, `workspace.py`, `event_handlers.py`**: **Contract**: These modules contain the handler functions for synchronous UI events. They must adhere to the **"Handler-Returns-Dict"** pattern, returning a dictionary of `gr.update()` objects keyed by `ComponentKey` enums.
* **`settings_manager.py`**: **Contract**: The single source of truth for UI settings. Manages default values, loading settings from files (`goan_settings.json`), and applying them to the UI with correct type casting.
* **`session_manager.py`**: **Contract**: Handles saving the application state on close (`goan_unload_save.json`) and restoring it on startup. It orchestrates calls to `settings_manager` to load the appropriate files.
* **`workspace.py`**: **Contract**: Contains UI handlers for workspace-level actions, such as "Save as Default" or downloading a workspace file. It acts as a thin layer, calling `settings_manager` or `session_manager` to perform the actual file operations. **Note**: This file is undergoing a major cleanup; much of its previous logic has been moved to the new managers.