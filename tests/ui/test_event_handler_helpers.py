import pytest
import gradio as gr
from src.ui.event_handler_helpers import handle_settings_menu_change
from src.ui.enums import ComponentKey as K

@pytest.fixture
def mock_app_state():
    """Fixture for a mock app_state."""
    return {"last_completed_video_path": "/path/to/test_video.mp4"}

def test_handle_settings_menu_change_power_user(mock_app_state):
    """Test visibility changes when 'Power User' menu is selected."""
    selected_menu = ["Power User"]
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP]['visible'] is True
    assert updates[K.LORA_GROUP]['visible'] is False
    assert updates[K.ADVANCED_SETTINGS_GROUP]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO]['value'] == "/path/to/test_video.mp4"
    assert updates[K.FULL_WIDTH_LAYOUT_ROW]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO_FULL_WIDTH]['value'] == "/path/to/test_video.mp4"
    assert updates[K.SETTINGS_MENU_CHECKBOX_GROUP]['value'] == ["Power User"]

def test_handle_settings_menu_change_lora(mock_app_state):
    """Test visibility changes when 'LoRA' menu is selected."""
    selected_menu = ["LoRA"]
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP]['visible'] is False
    assert updates[K.LORA_GROUP]['visible'] is True
    assert updates[K.ADVANCED_SETTINGS_GROUP]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO]['value'] == "/path/to/test_video.mp4"
    assert updates[K.FULL_WIDTH_LAYOUT_ROW]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO_FULL_WIDTH]['value'] == "/path/to/test_video.mp4"
    assert updates[K.SETTINGS_MENU_CHECKBOX_GROUP]['value'] == ["LoRA"]

def test_handle_settings_menu_change_advanced(mock_app_state):
    """Test visibility changes when 'Advanced' menu is selected."""
    selected_menu = ["Advanced"]
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP]['visible'] is False
    assert updates[K.LORA_GROUP]['visible'] is False
    assert updates[K.ADVANCED_SETTINGS_GROUP]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO]['value'] == "/path/to/test_video.mp4"
    assert updates[K.FULL_WIDTH_LAYOUT_ROW]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO_FULL_WIDTH]['value'] == "/path/to/test_video.mp4"
    assert updates[K.SETTINGS_MENU_CHECKBOX_GROUP]['value'] == ["Advanced"]

def test_handle_settings_menu_change_no_selection(mock_app_state):
    """Test visibility changes when no menu is selected."""
    selected_menu = []
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP]['visible'] is False
    assert updates[K.LORA_GROUP]['visible'] is False
    assert updates[K.ADVANCED_SETTINGS_GROUP]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO]['value'] == "/path/to/test_video.mp4"
    assert updates[K.FULL_WIDTH_LAYOUT_ROW]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO_FULL_WIDTH]['value'] == "/path/to/test_video.mp4"
    assert updates[K.SETTINGS_MENU_CHECKBOX_GROUP]['value'] == []

def test_handle_settings_menu_change_multiple_selection_prefers_last(mock_app_state):
    """Test that when multiple menus are selected, the last one is preferred."""
    selected_menu = ["Power User", "LoRA"]
    updates = handle_settings_menu_change(selected_menu, mock_app_state)

    assert updates[K.POWER_USER_GROUP]['visible'] is False
    assert updates[K.LORA_GROUP]['visible'] is True
    assert updates[K.ADVANCED_SETTINGS_GROUP]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO]['visible'] is True
    assert updates[K.LAST_FINISHED_VIDEO]['value'] == "/path/to/test_video.mp4"
    assert updates[K.FULL_WIDTH_LAYOUT_ROW]['visible'] is False
    assert updates[K.LAST_FINISHED_VIDEO_FULL_WIDTH]['value'] == "/path/to/test_video.mp4"
    assert updates[K.SETTINGS_MENU_CHECKBOX_GROUP]['value'] == ["LoRA"]