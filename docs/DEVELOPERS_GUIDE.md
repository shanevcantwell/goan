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
| **`QueueManager`** | Manages all operations on the task queue data structure. | `queue` (list), `processing` (bool), `editing_task_id` (int/None), `next_task_id` (int) |

---

## 2. Core Architecture Overview

The application can be understood as three main layers:

*   **Frontend (Gradio View Layer)**: Defined in `ui/layout.py`. This layer is responsible only for creating and arranging the Gradio components. It is a "dumb" layer with no event logic.

*   **Backend (Worker Engine)**: The `worker` function in `core/generation_core.py` is the heart of the generation process. It runs in a separate thread and is completely decoupled from Gradio. It accepts a dictionary of parameters and communicates its progress back to the `ProcessingAgent` via a dedicated message queue.

*   **UI Logic (The "Glue" Layer)**: This layer bridges the gap between the Frontend and the Backend and resides primarily in the `src/ui/` directory.
    *   **`ui/agents.py`**: Defines the `ProcessingAgent`, a singleton that orchestrates the backend. It receives commands (e.g., "start", "stop") via its `mailbox` and launches the `worker` in a separate thread. It is the sole consumer of the worker's output stream.
    *   **`ui/queue_processing.py`**: Contains the `process_task_queue_and_listen` generator. This function is the UI's main entry point for starting processing. It sends the "start" command to the agent and then enters a loop, consuming messages from the global `ui_update_queue` and `yield`ing updates to Gradio.
    *   **`ui/queue_manager.py`**: The thread-safe singleton for all queue data operations.
    *   **`ui/event_handlers.py`, `ui/queue.py`, `ui/workspace.py`**: These modules contain handler functions for synchronous UI events (e.g., adding a task, clearing an image). They directly call the `QueueManager` or other services and return tuples of `gr.update()` objects.
    *   **`switchboard_*.py` files**: These modules are responsible for wiring UI component events (e.g., `.click()`, `.upload()`) to their respective handler functions.

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

## 3. Key Process Flows

### Flow 1: Starting and Monitoring a Task Queue (Asynchronous)

1.  **User Action**: The user clicks the "Process Queue" button.
2.  **Switchboard**: The `.click()` event calls the `process_task_queue_and_listen` generator in `ui/queue_processing.py`.
3.  **UI Listener**: The generator sees that processing is not active and sends a `{"type": "start"}` message to the `ProcessingAgent`'s `mailbox`.
4.  **Agent**: The agent's `run` loop receives the message and calls `_handle_start`, which launches its `_processing_loop` in a new thread.
5.  **Processing Loop (Agent)**:
    *   It calls `queue_manager_instance.get_and_start_next_task()` to get the first pending task.
    *   It launches the `worker` function from `generation_core.py` in another thread using `async_run`. It passes a unique `AsyncStream` object to the worker for communication.
6.  **Worker**: The `worker` performs the generation. As it completes steps or segments, it calls `output_queue_ref.push(('flag', data))` to send status updates (e.g., `progress`, `file`) back to the agent.
7.  **Agent -> UI Bridge**: The agent's `_processing_loop` listens to the worker's `AsyncStream`. When it receives a message, it pushes that same message onto the global `ui_update_queue`.
8.  **UI Update**: The `process_task_queue_and_listen` generator's `while` loop, which has been waiting, receives the message from `ui_update_queue` and `yield`s a tuple of `gr.update()` objects to the Gradio frontend, updating the progress bar, preview image, etc.
9.  **Loop**: This cycle (Worker -> Agent -> UI Listener -> Gradio) repeats until the task is finished. The agent then either gets the next task or signals `queue_finished`.

### Flow 2: Stopping a Task (Interrupt-Driven)

`goan` supports two types of stops: a "soft stop" to cancel only the current task and proceed to the next, and a "hard stop" to terminate the entire queue.

1.  **User Action**: While a task is running, the user clicks either the "X" on the task row (soft stop) or the main "Stop Processing" button (hard stop).
2.  **Switchboard & UI Handlers**:
    *   For a **soft stop**, the `handle_queue_action_on_select` function in `ui/queue.py` sends a `{"type": "cancel_task"}` message to the `ProcessingAgent`.
    *   For a **hard stop**, the `process_task_queue_and_listen` function in `ui/queue_processing.py` sets the `stop_requested_flag` and sends a `{"type": "stop_queue"}` message.
3.  **Agent**:
    *   `_handle_cancel_task` sets only the `interrupt_flag`. The agent's processing loop will see this, finish the current task with an "aborted" status, and then simply proceed to the next task in the queue.
    *   `_handle_stop_queue` sets both the `interrupt_flag` (to stop the worker) and the `stop_requested_flag` (to terminate the agent's processing loop).
4.  **Worker**: The `worker` is designed to check `interrupt_flag.is_set()` frequently. When it detects the flag, it raises an `InterruptedError`.
5.  **Graceful Exit**: The `worker`'s main `try...except` block catches the `InterruptedError`, pushes a final `('aborted', ...)` message to its output queue, and cleans up.
6.  **Agent**: The agent's `_processing_loop` receives the `'aborted'` message. It calls `queue_manager_instance.complete_task()` to reset the task's status to `"pending"` (so it can be run again) and then pushes a `('task_finished', {"status": "aborted"})` message to the `ui_update_queue`.
7.  **UI Update**: The UI listener receives the `task_finished` signal and updates the UI to show the task was stopped, clearing progress bars and resetting button states.
 
### Flow 3: Requesting a Manual Preview (Event-Driven during Processing)

1.  **User Action**: While a task is processing, the user clicks the "Create Preview Now" button.
2.  **Switchboard**: The `.click()` event calls `toggle_manual_preview_action` in `event_handlers.py`.
3.  **Event Handler**: This function sets the `shared_state_instance.manual_preview_request_flag` and optimistically updates the button text to "Cancel Preview Request". If clicked again, it clears the flag and reverts the text.
4.  **Worker**: At the start of each new segment, the `worker` checks if `manual_preview_request_flag.is_set()`.
5.  **Preview Generation**: If the flag is set, the worker generates a preview for that segment (even if it wasn't automatically scheduled). It then calls `manual_preview_request_flag.clear()` to consume the request.
6.  **UI Update**: The worker pushes the preview file path to the agent via a `('file', ...)` message. The agent forwards this to the UI listener, which updates the video player in the UI.
7.  **Button State Reset**: The `ProcessingAgent` is also responsible for sending a UI update to reset the "Create Preview" button back to its default "Create Preview Now" state. This happens because the agent, upon receiving the next segment's progress, will see the flag is now clear and update the button accordingly.

---

## 4. UI State Logic: The Button State Machine

The interactivity of the main control buttons is managed by a single function, `update_button_states` in `event_handlers.py`. It acts as a state machine, deriving the application's current state and applying a set of rules to determine which buttons should be enabled or disabled.

| Application State | `Process Queue` Button | `Add Task` Button | `Create Preview` Button | Other Buttons |
| :--- | :--- | :--- | :--- | :--- |
| **Stopping** | `Stopping...` (disabled) | Disabled | Disabled | Disabled |
| **Editing Task** | Disabled | `Update Task` (enabled) | Disabled | `Cancel Edit` is visible/enabled. Others disabled. |
| **Processing** | `Stop Processing` (enabled) | Enabled (if image present) | Enabled (as a toggle) | `Clear Queue` enabled (if pending tasks exist). Others disabled. |
| **Idle** | Enabled (if queue has tasks) | Enabled (if image present) | Disabled | `Save Queue`, `Clear Queue`, `Clear/Download Image` enabled based on context. |

---

## 5. Notable Implementations

### Legacy GPU Support (Compute Capability < 8.0)

The application provides out-of-the-box support for older NVIDIA GPUs (Turing architecture, SM7.5) that lack `bfloat16` support. This is handled through a series of automated steps:

1.  **Detection**: On startup, `core/model_loader.py` checks the GPU's compute capability. If it's less than 8.0, it sets a global `is_legacy_gpu` flag in `shared_state_instance`.
2.  **Model Loading**: When the `transformer` is loaded, this flag forces its data type to `torch.float32` instead of the default `torch.bfloat16`, preventing data type errors on older hardware.
3.  **Inference**: The `worker` in `core/generation_core.py` also checks this flag and forces the `use_fp32_transformer_output` setting to `True`, ensuring stable inference. The corresponding UI checkbox is automatically hidden to prevent user confusion.

This approach, based on work by `@freely-boss`, ensures maximum compatibility without requiring any user intervention.

### LoRA Application and Reversion

The LoRA system is designed to be robust and flexible, handling the entire lifecycle of applying and reverting LoRA weights without leaving the models in a modified state. The core logic resides in the `LoRAManager` class in `src/ui/lora.py`.

*   **Multi-LoRA Support**: The UI provides 5 slots to apply LoRAs sequentially. The `ProcessingAgent` iterates through the configured slots and calls `apply_lora` for each one before the first task begins. This allows for blending and experimenting with multiple concepts.

*   **Lifecycle**: The `ProcessingAgent` creates a `LoRAManager` instance at the start of a queue run. It applies all configured LoRAs and ensures `revert_all_loras` is called in a `finally` block, guaranteeing that models are cleaned up even if an error occurs.

*   **Static Merging**: `goan` uses a static merging strategy. Instead of injecting adapter layers, it directly modifies the weights of the target model layers in memory.
    *   Before a weight is modified, its original state is cloned and stored in the `_original_params` dictionary.
    *   The LoRA's `down` and `up` weights are used to calculate a `delta_w` tensor, which is then added to the original weight.

*   **Key Name Translation & Compatibility**:
    *   **Automatic Translation**: A key feature is the `_convert_hunyuan_keys_to_framepack` function. Many "wild" LoRAs are trained using different conventions (e.g., `kohya-ss`). This function acts as a translator, intelligently renaming layers from common formats to match the specific architecture of the FramePack models. This includes complex operations like splitting a single `QKV` weight tensor from a LoRA into the separate `Q`, `K`, and `V` weights required by the model.
    *   **Model Mismatch**: While the translator improves compatibility, it's important to note that FramePack is a fine-tuned version of the base Hunyuan model. Applying a LoRA trained on the base Hunyuan model may produce unpredictable or unintended effects.
    *   **Unknown Keys**: The key translator is based on common LoRA formats. It is possible to encounter a LoRA with a novel key naming scheme that the translator does not recognize. In such cases, the LoRA may fail to apply to any layers.

*   **Device-Aware Reversion**: The `revert_all_loras` function is carefully designed to prevent device mismatch errors. When restoring a backed-up weight from CPU memory to a model that is currently on the GPU, it explicitly calls `.to(model_device)` on the parameter before assigning it. This prevents the common `RuntimeError: Expected all tensors to be on the same device...` that can occur in complex, memory-managed pipelines.

*   **UI Feedback**: To address the inconsistent nature of wild LoRAs, the `apply_lora` function provides immediate feedback to the user via a `gr.Info` or `gr.Warning` popup, reporting exactly how many layers were successfully merged. This instantly tells the user if a given LoRA is compatible with the selected model targets.

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
* **`queue.py`, `workspace.py`, `event_handlers.py`**: **Contract**: These modules contain the handler functions for synchronous UI events. Any function called directly by a switchboard event must return a tuple of `gr.update()` objects matching the length of the event's `outputs` list.