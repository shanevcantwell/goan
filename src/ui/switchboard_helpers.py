# src/ui/switchboard_helpers.py
import gradio as gr
import logging
from typing import Dict, List, Any

from src.ui.enums import ComponentKey
logger = logging.getLogger(__name__)

def apply_updates(update_dict: Dict[ComponentKey, Any], output_keys: List[ComponentKey], components_map: Dict[ComponentKey, gr.Component]) -> Any:
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

    2.  **Tactical Bug Fix**: It contains a workaround for a specific Gradio behavior
        where `gr.Number` and `gr.Slider` components might receive the `gr.update()`
        dict itself (e.g., `{'__type__': 'update', 'value': 42}`) instead of its
        'value' when passed through a `gr.State` component in a `.then()` chain. This
        causes a `TypeError`. The function inspects the target component and, if it's
        a Number or Slider, manually extracts the raw value from the update object.
    """
    if not isinstance(update_dict, dict):
        logger.warning(f"apply_updates expected a dict but got {type(update_dict)}. Returning no-op updates.")
        updates = [gr.update() for _ in output_keys]
        return updates[0] if len(updates) == 1 else updates

    result_list = []
    for key in output_keys:
        # Get the update object for the current key, defaulting to a no-op update.
        update_obj = update_dict.get(key, gr.update())

        # Default to passing the update object (or raw value) as is.
        value_to_append = update_obj

        # Check for the specific Gradio workaround condition.
        is_gradio_update = isinstance(update_obj, dict) and update_obj.get('__type__') == 'update'
        if is_gradio_update and key in components_map:
            target_component = components_map[key]
            if isinstance(target_component, (gr.Number, gr.Slider)):
                # For Number/Slider, we must extract the raw value from the update object.
                value_to_append = update_obj.get('value')

        result_list.append(value_to_append)

    # If there's only one output, return the single update object directly.
    # Otherwise, return the list of updates. This is crucial for Gradio's
    # handling of single vs. multiple outputs.
    return result_list[0] if len(result_list) == 1 else result_list
