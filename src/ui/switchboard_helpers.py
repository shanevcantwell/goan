# ui/switchboard_helpers.py
# Contains helper functions to simplify event wiring in switchboard modules.
import logging
import gradio as gr
from .enums import ComponentKey as K
from . import event_handlers

logger = logging.getLogger(__name__)

def chain_event_updates(event, components: dict, update_segments: bool = False):
    """
    Chains standard UI updates (buttons, segments) to a Gradio event.
    This helps to keep the switchboard modules DRY.

    Args:
        event: The Gradio event object to chain to (e.g., the result of a .click()).
        components (dict): The dictionary of all UI components.
        update_segments (bool): If True, chains the segment count update as well.
    """
    button_state_outputs = event_handlers.get_button_state_outputs(components)

    # Wrapper to absorb the payload from the preceding event.
    # The `update_button_states` function expects only one argument (the image),
    # but `event.then()` passes the event's output *before* the specified inputs.
    # This wrapper correctly calls the handler with only the argument it needs.
    def button_state_update_wrapper(*args):
        # The input_image_display value is the last argument.
        input_image_pil = args[-1]
        return event_handlers.update_button_states(input_image_pil)

    event.then(
        fn=button_state_update_wrapper,
        inputs=[components[K.INPUT_IMAGE_DISPLAY]],
        outputs=button_state_outputs
    )
    if update_segments:
        segment_recalc_inputs = [
            components[K.VIDEO_LENGTH_SLIDER],
            components[K.LATENT_WINDOW_SIZE_SLIDER],
            components[K.FPS_SLIDER]
        ]

        # The wrapper function is robustly designed to handle the event payload.
        # It accepts any number of arguments from the preceding event's output (*args)
        # and then calls the target function with only the specific inputs it needs.
        def segment_update_wrapper(*args):
            # The component values from `inputs` are always the last arguments.
            video_length, latent_window_size, fps = args[-len(segment_recalc_inputs):]
            return event_handlers.ui_update_total_segments(video_length, latent_window_size, fps)

        event.then(
            fn=segment_update_wrapper,
            # The `inputs` list should only contain UI components. The output from the
            # preceding `event` is piped implicitly as the first arguments to the function.
            inputs=segment_recalc_inputs,
            outputs=[components[K.TOTAL_SEGMENTS_DISPLAY]]
        )
