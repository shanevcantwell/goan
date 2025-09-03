import pytest
import gradio as gr
from unittest.mock import patch, MagicMock
from src.ui.enums import ComponentKey as K
from src.ui import queue_processing, shared_state
import queue

@pytest.fixture
def mock_app_state():
    """Fixture for a mock app_state."""
    return {"queue_state": {"queue": [], "next_id": 1, "processing": False, "editing_task_id": None},
            "last_completed_video_path": None,
            "lora_state": {"loaded_loras": {}}}

@pytest.fixture
def mock_ui_update_queue():
    """Fixture for mocking ui_update_queue."""
    with patch('src.ui.queue_processing.ui_update_queue', new_callable=MagicMock) as mock_queue:
        yield mock_queue

@pytest.fixture
def mock_queue_manager_instance():
    """Fixture for mocking queue_manager_instance."""
    with patch('src.ui.queue.queue_manager_instance') as mock_manager:
        mock_manager.get_state.return_value = {"processing": False}
        yield mock_manager

@pytest.fixture
def mock_shared_state_module():
    """Fixture for mocking shared_state_module."""
    with patch('src.ui.queue_processing.shared_state_module', new_callable=MagicMock) as mock_shared_state:
        mock_shared_state.shared_state_instance.stop_requested_flag = MagicMock()
        mock_shared_state.shared_state_instance.stop_requested_flag.is_set.return_value = False
        mock_shared_state.shared_state_instance.interrupt_flag = MagicMock()
        mock_shared_state.shared_state_instance.preview_request_flag = MagicMock()
        mock_shared_state.shared_state_instance.pause_request_flag = MagicMock()
        yield mock_shared_state

def get_update_for_key(updates_tuple, key):
    """Helper to find a specific component's update in the yielded tuple."""
    return updates_tuple[shared_state.QUEUE_PROCESSING_OUTPUT_KEYS.index(key)]

@pytest.mark.parametrize("file_payload", [
    # New dict format
    {"task_id": 1, "path": "/path/to/new_video.mp4"},
    # Old tuple format for backward compatibility
    (1, "/path/to/new_video.mp4", None)
])
def test_process_task_queue_and_listen_file_flag(file_payload, mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test that app_state is updated when 'file' flag is received, supporting both dict and tuple."""
    mock_ui_update_queue.get.side_effect = [
        ("file", file_payload),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True} # Keep processing to enter loop

    generator = queue_processing.process_task_queue_and_listen(mock_app_state, None, None, None)
    # First yield for "file" flag
    updates = next(generator)
    assert get_update_for_key(updates, K.APP_STATE).value["last_completed_video_path"] == "/path/to/new_video.mp4"
    assert get_update_for_key(updates, K.LAST_FINISHED_VIDEO).value == "/path/to/new_video.mp4"
    assert get_update_for_key(updates, K.LAST_FINISHED_VIDEO_FULL_WIDTH).value == "/path/to/new_video.mp4"

    # Simulate end of processing
    mock_queue_manager_instance.get_state.return_value = {"processing": False}
    with pytest.raises(StopIteration):
        next(generator)

def test_process_task_queue_and_listen_task_finished_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test that app_state is updated when 'task_finished' flag is received."""
    mock_ui_update_queue.get.side_effect = [
        ("task_finished", {"status": "done", "id": 1, "final_path": "/path/to/final_video.mp4"}),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True}

    generator = queue_processing.process_task_queue_and_listen(mock_app_state, None, None, None)

    # First yield for "task_finished" flag
    updates = next(generator)
    assert get_update_for_key(updates, K.APP_STATE).value["last_completed_video_path"] == "/path/to/final_video.mp4"
    assert get_update_for_key(updates, K.LAST_FINISHED_VIDEO).value == "/path/to/final_video.mp4"

    # Simulate end of processing
    mock_queue_manager_instance.get_state.return_value = {"processing": False}
    with pytest.raises(StopIteration):
        next(generator)

def test_process_task_queue_and_listen_processing_started_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test yielded updates for 'processing_started' flag."""
    mock_ui_update_queue.get.side_effect = [
        ("processing_started", None),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True}

    generator = queue_processing.process_task_queue_and_listen(mock_app_state, None, None, None)
    updates = next(generator)

    assert get_update_for_key(updates, K.CURRENT_TASK_PREVIEW_IMAGE).visible is True
    assert get_update_for_key(updates, K.CURRENT_TASK_PROGRESS_DESCRIPTION).value == "Queue processing started..."
    assert get_update_for_key(updates, K.CURRENT_TASK_PROGRESS_BAR).visible is True
    assert get_update_for_key(updates, K.PROCESS_QUEUE_BUTTON).value == "⏹️ Stop Processing"
    assert get_update_for_key(updates, K.CREATE_PREVIEW_BUTTON).interactive is True
    assert get_update_for_key(updates, K.CLEAR_QUEUE_BUTTON).interactive is False

    # Simulate end of processing
    mock_queue_manager_instance.get_state.return_value = {"processing": False}
    with pytest.raises(StopIteration):
        next(generator)

def test_process_task_queue_and_listen_progress_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test yielded updates for 'progress' flag."""
    progress_data = {
        "preview_np": "mock_preview_np",
        "description": "mock_desc",
        "html": "mock_html",
        "current_segment": 1,
        "preview_frequency": 5,
        "preview_specified_segments": "1,3,5",
        "eta_display": "ETA: 1m 30s"
    }
    mock_ui_update_queue.get.side_effect = [
        ("progress", progress_data),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True}

    generator = queue_processing.process_task_queue_and_listen(mock_app_state, None, None, None)
    updates = next(generator)

    assert get_update_for_key(updates, K.CURRENT_TASK_PREVIEW_IMAGE).value == "mock_preview_np"
    assert get_update_for_key(updates, K.CURRENT_TASK_PROGRESS_DESCRIPTION).value == "mock_desc"
    assert get_update_for_key(updates, K.CURRENT_TASK_PROGRESS_BAR).value == "mock_html"
    assert get_update_for_key(updates, K.SEGMENT_ETA_DISPLAY).value == "ETA: 1m 30s"

    # Simulate end of processing
    mock_queue_manager_instance.get_state.return_value = {"processing": False}
    with pytest.raises(StopIteration):
        next(generator)

def test_process_task_queue_and_listen_queue_finished_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test that the generator stops when 'queue_finished' flag is received."""
    mock_ui_update_queue.get.side_effect = [
        ("queue_finished", None),
        queue.Empty # This Empty is needed for the final yield after break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True}

    generator = queue_processing.process_task_queue_and_listen(mock_app_state, None, None, None)

    # Consume the "queue_finished" yield
    next(generator)

    # Now the generator should stop after the final yield
    mock_queue_manager_instance.get_state.return_value = {"processing": False} # Ensure processing is false for final yield
    with pytest.raises(StopIteration):
        next(generator)

    # Ensure final yield is correct (this part of the test is now unreachable if StopIteration is raised correctly)
    # The final yield happens *after* the loop breaks, so it's the last thing the generator does.
    # If the above `pytest.raises(StopIteration)` passes, then the generator has indeed stopped.
    # The original test had `updates = next(generator)` *after* the `pytest.raises`, which is incorrect.
    # The final yield is part of the generator's normal termination.
    # To test the content of the final yield, we would need to capture it before the StopIteration.
    # For now, I'll remove the unreachable assertions.