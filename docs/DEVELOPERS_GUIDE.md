# Developer's Guide to Extending 'goan'

## 1. Introduction & Core Philosophy

This document provides a technical overview of the `goan` application architecture. It is intended for developers looking to understand, maintain, or extend the codebase.

The application is built on four core principles:

1.  **Separation of Concerns**: The user interface (UI) is strictly separated from the backend generation engine via a formal API contract. The backend's role is to expose its capabilities through API endpoints, while the client's role is to consume this API to capture user intent and display results.
2.  **Centralized State Management**:
    *   **`SharedState`**: A singleton holding global, thread-safe state like threading events (`interrupt_flag`), loaded PyTorch models, and system info.
    *   **`QueueManager`**: A thread-safe singleton that exclusively manages the task queue's data and state (adding, removing, reordering, etc.).
3.  **Agent-Based Backend Orchestration**: A central `ProcessingAgent` singleton manages the entire lifecycle of the backend `worker` thread. This decouples the long-running generation process from the stateless API request/response cycle.
4.  **Asynchronous Event Broadcasting**: All communication from the backend worker to clients is funneled through the `ProcessingAgent` to a singleton `SSEManager`. This manager broadcasts real-time progress and status updates to all connected clients via Server-Sent Events (SSE), enabling a reactive and scalable frontend experience.

---

### State Management at a Glance

| Component | Responsibility | Key State Attributes |
| :--- | :--- | :--- |
| **`SharedState`** | Holds global, thread-safe application state and threading events. | `interrupt_flag`, `stop_requested_flag`, `manual_preview_request_flag`, `pause_request_flag`, `models` (dict), `system_info` (dict) |
| **`QueueManager`** | Manages all operations on the task queue data structure. Responsible for orchestrating the saving and loading of the queue to/from disk for session persistence. | `queue` (list), `processing` (bool), `next_task_id` (int) |

---

## 2. Core Architecture Overview

The application is now understood as two primary layers with a clear API boundary.

*   **Backend (API & Generation Engine)**: This layer contains all business logic, state management, and the core generation `worker`.
    *   **`api/` Layer**: A FastAPI application that defines all public-facing endpoints. It uses Pydantic models for strict data validation and delegates all actions to the `GoanAPI` singleton.
    *   **`GoanAPI` Singleton**: A UI-agnostic class that serves as the bridge between the web layer and the backend core. It provides a clean, programmatic interface to the `ProcessingAgent` and `QueueManager`.
    *   **`core/` Layer**: The heart of the generation process. The `worker` function runs in a separate thread, managed by the `ProcessingAgent`, and is completely decoupled from the API.

*   **Frontend (Client/UI Layer)**: This layer is any application that consumes the `goan` API. It is responsible for all aspects of the user interface and experience.
    *   **For a detailed guide on how to build a client that correctly maps UI concepts to the API schemas, please refer to the `UIUX_GUIDE.md` document.**

---

### Agent & Worker Communication

Communication between the API, the agent, and the worker is handled via message passing and events.

| Sender | Receiver | Message / Event | Purpose |
| :--- | :--- | :--- | :--- |
| **API Client** | `GoanAPI` (via FastAPI) | `POST /api/processing/start` | Start processing the task queue. |
| **API Client** | `GoanAPI` (via FastAPI) | `POST /api/processing/stop` | Request a hard stop of the entire queue. |
| **`worker`** | `ProcessingAgent` | `('progress', data)` | Send real-time progress updates. |
| **`worker`** | `ProcessingAgent` | `('file', data)` | Notify that a preview or final video file has been saved. |
| **`worker`** | `ProcessingAgent` | `('end', data)` | Signal that the task has completed successfully. |
| **`worker`** | `ProcessingAgent` | `('error', data)` | Signal that a fatal error occurred. |
| **`ProcessingAgent`** | `SSEManager` | `broadcast('progress', data)` | Forward progress updates to all connected clients. |
| **`ProcessingAgent`** | **`worker`** | `interrupt_flag.set()` | Signal the worker to perform an immediate, hard stop. |

---

## 3. Key Process Flows (Summarized)

*   **Starting a Task**: A user action on the client triggers a `POST` request to `/api/processing/start`. The `GoanAPI` instance sends a "start" message to the `ProcessingAgent`. The agent launches the `worker` in a new thread. The worker pushes progress updates back to the agent, which forwards them to the `SSEManager`. The `SSEManager` broadcasts these updates to all clients connected to the `/api/stream` endpoint.

*   **Stopping a Task**: A user action triggers a `POST` request to `/api/processing/stop`. The `GoanAPI` instance sends a "stop" message to the `ProcessingAgent`, which sets the `interrupt_flag`. The `worker` frequently checks this flag, raises an `InterruptedError` upon detection, and exits gracefully.

*   **Manual Preview**: A user action triggers a `POST` request to a dedicated preview endpoint (e.g., `/api/processing/preview`). The `GoanAPI` instance sets the `manual_preview_request_flag`. The `worker` checks this flag at the start of each segment, generates a preview if set, and then clears the flag.

---

## 4. UI State Management (Client-Side Responsibility)

With the move to a decoupled architecture, all UI state logic is now the exclusive responsibility of the client application. The backend is stateless from the perspective of the UI.

A client should manage its state (e.g., which buttons are enabled, what progress to display) by:
1.  Periodically fetching the overall queue state via a `GET` request to `/api/queue`.
2.  Maintaining a persistent connection to the `/api/stream` SSE endpoint to receive real-time events that trigger UI updates.

The complex server-side state machine (`update_button_states`) from the previous architecture is now deprecated and its logic should be reimplemented on the client.

---

## 5. Notable Implementations

### Legacy GPU Support (Compute Capability < 8.0)

(This section remains unchanged as it describes a core backend feature.)

### PNG Metadata

The application allows users to save and load their exact generation settings by embedding them in an image's metadata.

*   **Saving a Recipe**:
    1.  The client gathers all relevant parameters from its UI controls into a dictionary.
    2.  The client sends this data to a backend endpoint (e.g., `/api/image/prepare-download`).
    3.  The backend's `prepare_image_with_metadata` function serializes the dictionary into a JSON string and saves it into the PNG's metadata using the `Pillow` library, returning the new image bytes.

*   **Loading a Recipe**:
    1.  A user uploads a PNG file to the client application.
    2.  The client is responsible for reading the PNG's metadata and looking for the `goan_params` key. This can be done client-side or via a helper endpoint on the backend.
    3.  If found, the client parses the parameters and uses them to populate its own UI.
    4.  **Refer to the `UIUX_GUIDE.md` for a detailed breakdown of how UI concepts map to the parameter schema.**

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

(This section remains unchanged as it describes a core backend feature.)

---

## 6. Module Contracts (File-by-File)

### `src/core/` - The Backend Engine

* **`generation_core.py`**: **Contract**: Defines the `worker` function. It must be self-contained and must not import any API-level modules. It communicates *only* through the `output_queue_ref` passed to it by the `ProcessingAgent`.
* **`model_loader.py`**: **Contract**: Responsible for loading all PyTorch models, detecting hardware capabilities, and storing references in `shared_state_instance`.
* **`generation_utils.py`**: **Contract**: Contains helper functions for the `worker`.

### `src/api/` - The API Layer

* **`main_api.py`**: **Contract**: Defines all FastAPI endpoints. Handles HTTP request/response logic and validation. Must delegate all business logic to the `goan_api_instance`.
* **`core_api.py`**: **Contract**: Defines the `GoanAPI` singleton. Provides a stable, UI-agnostic, programmatic interface to the application's backend core (`ProcessingAgent`, `QueueManager`, etc.). This is the sole entry point for the API layer into the backend.
* **`pydantic_models.py`**: **Contract**: Defines the strict, versioned data schemas for all API communication. This is the public data contract for all clients.
* **`sse_manager.py`**: **Contract**: Defines the `SSEManager` singleton. Manages all active SSE client connections and provides a simple `broadcast` method for the backend to send events.

### `src/ui/` - Backend Support Modules

**Note**: The `ui` directory is a legacy name. It no longer contains UI components but rather core backend singletons and logic that were previously coupled to the Gradio UI.

* **`enums.py`**: **Contract**: Defines core application enums like `UIMessage` and `TaskStatus`.
* **`shared_state.py`**: **Contract**: Defines the `SharedState` singleton and global threading primitives.
* **`agents.py`**: **Contract**: Defines the `ProcessingAgent`. Its sole responsibility is to manage the lifecycle of the `worker` thread and bridge communication between the `GoanAPI` and the worker.
* **`queue_manager.py`**: **Contract**: Implements the `QueueManager` singleton. This is the **only** class that should directly modify the queue's internal state (`self.state["queue"]`).
* **`settings_manager.py` & `session_manager.py`**: **Contract**: These modules manage the persistence of settings and session state to/from JSON files on the server. They are invoked by the `GoanAPI` for persistence operations.
* **Deprecated Modules**: `layout.py`, `switchboard_*.py`, `queue_processing.py`, and the various `event_handlers.py` files are now **deprecated**. Their functionality has been replaced by the FastAPI endpoints and the client-side logic described in the `UIUX_GUIDE.md`.
