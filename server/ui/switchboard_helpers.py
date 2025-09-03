# src/ui/switchboard_helpers.py
import gradio as gr
import logging
from typing import Dict, List, Any

from src.ui.enums import ComponentKey
logger = logging.getLogger(__name__)

def apply_updates(update_dict: Dict[ComponentKey, Any], output_keys: List[ComponentKey], components_map: Dict[ComponentKey, gr.Component]) -> Any | List:
    """
    A helper function that serves two critical roles in the application's UI architecture.

    It returns a list of updates for multiple outputs, or a single update object
    for a single output, to comply with Gradio's event return value requirements.
    This prevents `AttributeError` crashes when a single-item list is returned
    for a single output component (e.g., a `gr.Markdown` component).

    1.  **Architectural Bridge**: It enables the "Handler-Returns-Dict" pattern. Gradio's
        event system requires a handler to return a list of updates in a specific,
        fixed order. This function acts as a bridge, taking an order-agnostic
        dictionary from a handler and an ordered list of component keys from the
        switchboard, and producing the correctly ordered list of updates that Gradio expects.
        This decouples business logic from UI layout, making the code more robust.
    """
    if not isinstance(update_dict, dict):
        logger.warning(f"apply_updates expected a dict but got {type(update_dict)}. Returning no-op updates.")
        updates = [gr.update() for _ in output_keys]
        return updates[0] if len(updates) == 1 else updates

    result_list = [
        # Get the update object for the current key, defaulting to a no-op update.
        update_dict.get(key, gr.update())
        for key in output_keys
    ]

    # If there's only one output, return the single update object directly.
    # Otherwise, return the list of updates. This is crucial for Gradio's
    # handling of single vs. multiple outputs.
    return result_list[0] if len(result_list) == 1 else result_list
