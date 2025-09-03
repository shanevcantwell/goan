import pytest
import gradio as gr
from unittest.mock import MagicMock, patch
from src.ui.switchboard_queue import wire_events
from src.ui.enums import ComponentKey as K

@pytest.fixture
def mock_components():
    """Fixture for mocking Gradio components."""
    components = {}
    for key in K:
        mock_comp = MagicMock()
        mock_comp.click.return_value = mock_comp # Allow chaining .click().then()
        mock_comp.then.return_value = mock_comp
        mock_comp.upload.return_value = mock_comp
        mock_comp.select.return_value = mock_comp
        components[key] = mock_comp
    return components

@patch('src.ui.switchboard_queue.queue_actions')
@patch('src.ui.switchboard_queue.queue_processing')
@patch('src.ui.switchboard_queue.event_handlers')
@patch('src.ui.switchboard_queue.event_handler_helpers')
@patch('src.ui.switchboard_queue.shared_state_module')
def test_wire_events_no_errors(mock_shared_state_module, mock_event_handler_helpers, mock_event_handlers, mock_queue_processing, mock_queue_actions, mock_components):
    """Test that wire_events runs without errors and calls expected methods."""
    # Mock necessary attributes for shared_state_module
    mock_shared_state_module.ALL_TASK_UI_KEYS = [K.POSITIVE_PROMPT, K.NEGATIVE_PROMPT]
    mock_event_handler_helpers.BUTTON_KEYS = [K.ADD_TASK_BUTTON, K.PROCESS_QUEUE_BUTTON]

    wire_events(mock_components)

    # Verify that click and then methods are called on relevant components
    mock_components[K.ADD_TASK_BUTTON].click.assert_called_once()
    mock_components[K.ADD_TASK_BUTTON].then.assert_called_once()
    mock_components[K.PROCESS_QUEUE_BUTTON].click.assert_called_once()
    mock_components[K.PROCESS_QUEUE_BUTTON].then.assert_called_once()
    mock_components[K.CREATE_PREVIEW_BUTTON].click.assert_called_once()
    mock_components[K.CREATE_PREVIEW_BUTTON].then.assert_called_once()
    mock_components[K.CLEAR_QUEUE_BUTTON].click.assert_called_once()
    mock_components[K.CLEAR_QUEUE_BUTTON].then.assert_called_once()
    mock_components[K.LOAD_QUEUE_BUTTON].upload.assert_called_once()
    mock_components[K.LOAD_QUEUE_BUTTON].then.assert_called_once()
    mock_components[K.QUEUE_DF].select.assert_called_once()
    mock_components[K.QUEUE_DF].then.assert_called_once()

    # Verify that the correct functions are assigned (mocked functions)
    # This is a basic check, more detailed checks would involve inspecting call arguments
    mock_components[K.ADD_TASK_BUTTON].click.assert_called_with(
        fn=mock_queue_actions.add_or_update_task_in_queue,
        inputs=pytest.any_args, # We're not testing inputs here, just that it's called
        outputs=pytest.any_args,
        api_name="add_task"
    )
    mock_components[K.PROCESS_QUEUE_BUTTON].then.assert_called_with(
        fn=mock_queue_processing.process_task_queue_and_listen,
        inputs=pytest.any_args,
        outputs=pytest.any_args
    )