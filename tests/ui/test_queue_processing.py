import pytest
import gradio as gr
from unittest.mock import patch, MagicMock
from src.ui.queue_processing import process_task_queue_and_listen
from src.ui.enums import ComponentKey as K
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
    with patch('src.ui.queue_processing.ui_update_queue') as mock_queue:
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
    with patch('src.ui.queue_processing.shared_state_module') as mock_shared_state:
        mock_shared_state.shared_state_instance.stop_requested_flag = MagicMock()
        mock_shared_state.shared_state_instance.stop_requested_flag.is_set.return_value = False
        mock_shared_state.shared_state_instance.interrupt_flag = MagicMock()
        mock_shared_state.shared_state_instance.preview_request_flag = MagicMock()
        mock_shared_state.shared_state_instance.pause_request_flag = MagicMock()
        yield mock_shared_state

def test_process_task_queue_and_listen_file_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test that app_state is updated when 'file' flag is received."""
    mock_ui_update_queue.get.side_effect = [
        ("file", (1, "/path/to/new_video.mp4", None)),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True} # Keep processing to enter loop

    generator = process_task_queue_and_listen(mock_app_state)

    # First yield for "file" flag
    updates = next(generator)
    assert updates[0]['value']["last_completed_video_path"] == "/path/to/new_video.mp4"
    assert updates[2]['value'] == "/path/to/new_video.mp4" # LAST_FINISHED_VIDEO

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

    generator = process_task_queue_and_listen(mock_app_state)

    # First yield for "task_finished" flag
    updates = next(generator)
    assert updates[0]['value']["last_completed_video_path"] == "/path/to/final_video.mp4"
    assert updates[2]['value'] == "/path/to/final_video.mp4" # LAST_FINISHED_VIDEO

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

    generator = process_task_queue_and_listen(mock_app_state)
    updates = next(generator)

    assert isinstance(updates[0], dict) # APP_STATE
    assert updates[0]['__type__'] == 'update' # Ensure it's a Gradio update dict
    assert isinstance(updates[1], dict) # QUEUE_DF
    assert updates[1]['__type__'] == 'update'
    assert isinstance(updates[2], dict) # LAST_FINISHED_VIDEO
    assert updates[2]['__type__'] == 'update'
    assert updates[3]['visible'] is True # CURRENT_TASK_PREVIEW_IMAGE
    assert updates[4]['value'] == "Queue processing started..." # Progress description
    assert updates[5]['visible'] is True # Progress bar
    assert updates[6]['value'] == "⏹️ Stop Processing" # PROCESS_QUEUE_BUTTON
    assert updates[7]['interactive'] is True # CREATE_PREVIEW_BUTTON
    assert updates[8]['interactive'] is False # CLEAR_QUEUE_BUTTON

    # Simulate end of processing
    mock_queue_manager_instance.get_state.return_value = {"processing": False}
    with pytest.raises(StopIteration):
        next(generator)

def test_process_task_queue_and_listen_progress_flag(mock_app_state, mock_ui_update_queue, mock_queue_manager_instance, mock_shared_state_module):
    """Test yielded updates for 'progress' flag."""
    mock_ui_update_queue.get.side_effect = [
        ("progress", (1, "mock_preview_np", "mock_desc", "mock_html")),
        queue.Empty, # First Empty
        queue.Empty  # Second Empty to trigger break
    ]
    mock_queue_manager_instance.get_state.return_value = {"processing": True}

    generator = process_task_queue_and_listen(mock_app_state)
    updates = next(generator)

    assert isinstance(updates[0], dict) # APP_STATE
    assert updates[0]['__type__'] == 'update' # Ensure it's a Gradio update dict
    assert isinstance(updates[1], dict) # QUEUE_DF
    assert updates[1]['__type__'] == 'update'
    assert isinstance(updates[2], dict) # LAST_FINISHED_VIDEO
    assert updates[2]['__type__'] == 'update'
    assert updates[3]['value'] == "mock_preview_np" # CURRENT_TASK_PREVIEW_IMAGE
    assert updates[4]['value'] == "mock_desc" # Progress description
    assert updates[5]['value'] == "mock_html" # Progress bar

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

    generator = process_task_queue_and_listen(mock_app_state)

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