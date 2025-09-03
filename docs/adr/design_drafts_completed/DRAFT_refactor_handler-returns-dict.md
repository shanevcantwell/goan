---
# Design Doc: Multi-User Architecture and Stateless I/O

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-06
-   **Status**: Completed

---


# Refactor Status & Completion Guide: "Handler-Returns-Dict" Architecture

## 1. Objective

The goal of this refactor is to overhaul the Gradio event handling logic across the entire `goan` application. We will replace the current brittle system, where handler functions must return perfectly ordered tuples of updates, with a robust and maintainable **"Handler-Returns-Dict"** pattern.

This will eliminate `ValueError` exceptions caused by return signature mismatches, remove "magic numbers," and formally decouple the business logic (handlers) from the UI wiring (switchboards).

---

## 1.5. Refactor Summary & Outcome

**This refactor is complete.** The "Handler-Returns-Dict" pattern has been successfully implemented across the entire application.

The primary outcome of this effort was the successful dismantling of the `workspace.py` "god object." Its responsibilities were cleanly separated into two new, single-responsibility modules:

*   `settings_manager.py`: For default values and `goan_settings.json`.
*   `session_manager.py`: For saving/restoring the session via `goan_unload_save.json`.

All UI event handlers now return a dictionary of updates, and the switchboard modules correctly map these dictionaries to the UI components. This has eliminated a significant source of `ValueError` exceptions and has made the codebase substantially more robust, maintainable, and easier to extend.


---

## 2. The Architectural Pattern

The new architecture consists of two parts:

* **The Handler Function**:
    * **Contract**: A function responsible for a specific action (e.g., processing a file, adding a task).
    * **Return Value**: It **must** return a single Python `dict`. The keys of this dictionary are `ComponentKey` enums, and the values are the corresponding `gr.update()` objects. The handler no longer needs to know the number or order of UI components.

* **The Switchboard Wiring**:
    * **Contract**: The switchboard module is the **single source of truth** for which UI components an event affects. It uses the `ComponentKey` enum defined in `src/ui/enums.py` to identify UI components in a type-safe manner. **This `enums.py` file acts as the central contract for the keys used in the dictionaries returned by handler functions.**
    * **Implementation**: It defines the list of component keys for an event's outputs. It uses a helper function in a `.then()` block to map the dictionary returned by the handler to this list of components.

---