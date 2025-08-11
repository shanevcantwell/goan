import pytest
import gradio as gr
from src.ui.layout import create_ui
from src.ui.enums import ComponentKey as K

def test_create_ui_returns_dict():
    """Test that create_ui returns a dictionary."""
    components = create_ui()
    assert isinstance(components, dict)

def test_create_ui_contains_expected_components():
    """Test that the returned dictionary contains essential components."""
    components = create_ui()
    assert K.BLOCK in components
    assert isinstance(components[K.BLOCK], gr.Blocks)
    assert K.APP_STATE in components
    assert isinstance(components[K.APP_STATE], gr.State)
    assert K.LAST_FINISHED_VIDEO in components
    assert isinstance(components[K.LAST_FINISHED_VIDEO], gr.Video)
    assert K.LAST_FINISHED_VIDEO_FULL_WIDTH in components
    assert isinstance(components[K.LAST_FINISHED_VIDEO_FULL_WIDTH], gr.Video)