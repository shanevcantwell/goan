# Design Doc: In-Queue Task Editing

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-11
-   **Status**: Design Complete

---

## 1. Summary

This document outlines the design and process flow for the "Edit Task" feature. The goal is to allow a user to modify the parameters of a task that is already in the generation queue without needing to delete and recreate it. This provides a more fluid and efficient user workflow.

---

## 2. User Story

As a user, I want to select a task in my queue and adjust its settings (like the prompt, seed, or CFG scale) directly. After making my changes, I want to save them back to the task in the queue, so I can quickly correct mistakes or experiment with variations without disrupting my workflow.

---

## 3. Core Mechanism: Modal Editing State

The editing feature is built around a modal application state managed by the `QueueManager` singleton. The application can be in one of three primary states regarding the queue: `Idle`, `Processing`, or `Editing`. The `Editing` state is mutually exclusive with `Processing`.

*   **State Trigger**: The state is entered when the `QueueManager`'s `editing_task_id` attribute is set to the ID of the task being edited. When it is `None`, the application is not in editing mode.

*   **UI Reconfiguration**: The `update_button_states` function in `ui/event_handlers.py` is the state machine responsible for reconfiguring the UI when the `Editing` state is active. It disables irrelevant controls (like "Process Queue") and changes the "Add Task" button to "Update Task", making the user's path clear.

---

## 4. Process Flow

The end-to-end process for editing a task involves a coordinated effort between the UI, event handlers, and the `QueueManager`.

1.  **User Initiates Edit**: The user clicks the "Edit" button associated with a specific task in the queue UI.

2.  **Handler Calls Manager**: An event handler in `ui/queue.py` is triggered. It calls `queue_manager_instance.start_editing_task(task_id)`.

3.  **`QueueManager` Enters Editing State**:
    *   The `QueueManager` sets its internal `editing_task_id` to the `task_id`.
    *   It retrieves the parameters for that task from its internal queue.
    *   It returns a dictionary of `gr.update()` objects containing the task's parameters.

4.  **UI Populates with Task Data**: The `switchboard` wires the handler's return dictionary to the creative UI controls, populating them with the data from the task being edited.

5.  **Button State Machine Reacts**: The `update_button_states` function is triggered. It detects that `editing_task_id` is set and reconfigures the UI buttons for editing mode (e.g., "Add Task" becomes "Update Task", "Process Queue" is disabled).

6.  **User Modifies & Saves**: The user adjusts the parameters in the UI and clicks the "Update Task" button.

7.  **Handler Commits Changes**: The "Update Task" button's event handler collects the current values from all creative UI controls and calls `queue_manager_instance.finish_editing_task(updated_params)`.

8.  **`QueueManager` Finalizes Edit**:
    *   The `QueueManager` finds the task in its internal queue using the stored `editing_task_id`.
    *   It updates the task's dictionary with the `updated_params`.
    *   It resets `editing_task_id` to `None`, exiting the editing state.

9.  **UI Returns to Idle State**: The `update_button_states` function runs again, detects that `editing_task_id` is now `None`, and restores the buttons to their normal idle or processing state. The queue UI automatically reflects the updated task parameters.

---

## 5. Key Component Responsibilities

*   **`src/ui/queue_manager.py`**:
    *   Owns the `editing_task_id` state variable.
    *   Provides the `start_editing_task(task_id)` and `finish_editing_task(params)` methods, which are the sole entry and exit points for the editing state logic.
    *   Handles the data retrieval and commitment to its internal queue data structure.

*   **`src/ui/event_handlers.py`**:
    *   The `update_button_states` function acts as the UI reflection of the `QueueManager`'s state, ensuring a clear and non-confusing user experience by enabling, disabling, and relabeling buttons as needed.

*   **`src/ui/queue.py`**:
    *   Contains the Gradio event handler functions that are called directly by user actions (clicking "Edit" or "Update Task"). These handlers act as a thin layer to orchestrate calls to the `QueueManager`.

*   **`src/ui/switchboard_queue.py`**:
    *   Responsible for wiring the `.click()` events of the dynamically generated "Edit" buttons and the main "Update Task" button to their respective handlers in `queue.py`.