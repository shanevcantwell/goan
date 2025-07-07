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

1.  **User Action**: While a task is running, the user clicks the "Stop Processing" button.
2.  **Switchboard**: The `.click()` event again calls `process_task_queue_and_listen`.
3.  **UI Listener**: This time, the function sees that `processing` is `True`. It sets a `stop_requested_flag` for immediate UI feedback (disabling other buttons) and sends a `{"type": "stop"}` message to the `ProcessingAgent`.
4.  **Agent**: The agent's `_handle_stop` method sets the global `shared_state_instance.interrupt_flag`.
5.  **Worker**: The `worker` is designed to check `interrupt_flag.is_set()` frequently (between segments and within the sampling loop). When it detects the flag, it raises an `InterruptedError`.
6.  **Graceful Exit**: The `worker`'s main `try...except` block catches the `InterruptedError`, pushes a final `('aborted', ...)` message to its output queue, and cleans up.
7.  **Agent**: The agent's `_processing_loop` receives the `'aborted'` message. It calls `queue_manager_instance.complete_task()` to reset the task's status to `"pending"` (so it can be run again) and then pushes a `('task_finished', {"status": "aborted"})` message to the `ui_update_queue`.
8.  **UI Update**: The UI listener receives the `task_finished` signal and updates the UI to show the task was stopped, clearing progress bars and resetting button states.
 
### Flow 3: Requesting a Manual Preview (Event-Driven during Processing)

1.  **User Action**: While a task is processing, the

---

## 4. Module Contracts (File-by-File)

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