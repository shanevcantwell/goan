# goan Testing Guide

This guide provides instructions on how to set up and run unit tests for the `goan` project, and offers guidance on writing new tests, especially for Gradio-based UI components and asynchronous server-side logic.

## 1. Setting Up the Testing Environment

To run tests, you need to have `pytest` installed in your project's virtual environment and ensure that the project's source code is discoverable by the Python interpreter.

### 1.1 Install pytest

First, activate your virtual environment (if you haven't already) and install `pytest`:

```bash
# Navigate to your project root
cd /path/to/your/goan-development

# Activate the virtual environment
source .venv_goan/bin/activate # For Linux/macOS
# .venv_goan\\Scripts\\activate # For Windows (in PowerShell)

# Install pytest
pip install pytest
```

### 1.2 Configure PYTHONPATH

The `goan` project structure places source code in the `src/` directory. To allow `pytest` to import modules from `src/`, you need to add the `src/` directory to your `PYTHONPATH` environment variable.

```bash
# From your project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

You can add this line to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`) to make it permanent, or include it in a test-running script.

## 2. Running Tests

Once your environment is set up, you can run tests using the `pytest` command.

### 2.1 Run All Tests

To run all tests in the project:

```bash
pytest
```

### 2.2 Run Tests in a Specific File

To run tests contained within a specific test file:

```bash
pytest tests/ui/test_layout.py
```

### 2.3 Run Specific Tests

To run a specific test function within a file:

```bash
pytest tests/ui/test_layout.py::test_create_ui_returns_dict
```

## 3. Writing New Tests

When writing new tests for `goan`, consider the following patterns, especially for Gradio UI components and asynchronous server logic.

### 3.1 Testing Gradio UI Components

Gradio components often involve complex interactions and state management. When writing unit tests, you'll typically mock Gradio components and their methods to isolate the logic you're testing.

-   **Mocking Components**: Use `unittest.mock.MagicMock` to create mock Gradio components. This allows you to simulate their behavior and assert that their methods are called correctly.
-   **Mocking `gr.update()`**: When a function returns `gr.update()`, you can inspect the attributes of the returned object (e.g., `updates.visible`, `updates.value`) to verify the intended UI changes.

**Example (from `test_layout.py`):**

```python
import gradio as gr
from src.ui.layout import create_ui
from src.ui.enums import ComponentKey as K

def test_create_ui_contains_expected_components():
    components = create_ui()
    assert K.BLOCK in components
    assert isinstance(components[K.BLOCK], gr.Blocks)
    # ... and so on for other components
```

**Example (from `test_event_handler_helpers.py`):**

```python
import gradio as gr
from src.ui.event_handler_helpers import handle_settings_menu_change
from src.ui.enums import ComponentKey as K

def test_handle_settings_menu_change_power_user(mock_app_state):
    selected_menu = ["Power User"]
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP].visible is True
    assert updates[K.LAST_FINISHED_VIDEO].visible is True
    assert updates[K.LAST_FINISHED_VIDEO].value == "/path/to/test_video.mp4"
    # ... and so on for other assertions
```

### 3.2 Testing Asynchronous Server Logic (Generators and Queues)

The `goan` application uses a generator-based approach (`process_task_queue_and_listen`) to handle asynchronous updates from the backend `ProcessingAgent`. Testing such components requires careful mocking of queues and iteration through the generator's yielded values.

-   **Mocking Queues**: Use `unittest.mock.patch` to replace `queue.Queue` instances (like `ui_update_queue`) with `MagicMock` objects. You can then control what `get()` returns using `side_effect`.
-   **Iterating Generators**: Use `next()` to step through the generator's execution and `pytest.raises(StopIteration)` to confirm when the generator is expected to finish.
-   **Mocking Dependencies**: Mock external dependencies like `queue_manager_instance` and `shared_state_module` to control their behavior during tests.

**Example (from `test_queue_processing.py`):**

```python
import pytest
import gradio as gr
from unittest.mock import patch, MagicMock
from src.ui.queue_processing import process_task_queue_and_listen
import queue

@pytest.fixture
def mock_ui_update_queue():
    with patch('src.ui.queue_processing.ui_update_queue') as mock_queue:
        yield mock_queue

def test_process_task_queue_and_listen_file_flag(mock_app_state, mock_ui_update_queue, ...):
    mock_ui_update_queue.get.side_effect = [
        ("file", (1, "/path/to/new_video.mp4", None)),
        queue.Empty
    ]
    generator = process_task_queue_and_listen(mock_app_state, ...)

    updates = next(generator)
    assert updates[0].value["last_completed_video_path"] == "/path/to/new_video.mp4"
    # ... and so on for other assertions and iterations
```

By following these guidelines, you can effectively test the `goan` application's functionality and ensure its stability.

```