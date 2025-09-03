# src/ui/workspace.py
# Contains UI handlers for managing workspace files (e.g., saving defaults, loading recipes).

import gradio as gr
import json
import os
import tempfile
import logging

from . import shared_state as shared_state_module
from .enums import ComponentKey as K
from .settings_manager import settings_manager_instance

logger = logging.getLogger(__name__)

def save_as_default_workspace(*all_ui_inputs):
    """
    Saves the current UI settings as the default startup configuration. This acts
    as a thin UI handler that calls the settings_manager.
    """
    # This handler now acts as a thin wrapper. It passes all UI inputs to the
    # settings manager, which is responsible for filtering and saving.
    settings_manager_instance.save_default_settings_from_ui(all_ui_inputs)

    # Return a dictionary of updates.
    return {
        K.RELAUNCH_NOTIFICATION_MD: gr.update(visible=True)
    }