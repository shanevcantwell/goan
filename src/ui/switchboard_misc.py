import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import event_handlers
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def handle_scheduler_visibility_change(choice: str):
    """
    Handler that returns a dictionary of updates to show/hide scheduler sliders
    based on the selected schedule type.
    """
    is_linear = (choice == "Linear")
    is_rolloff = (choice == "Roll-off")
    show_final_gs = is_linear or is_rolloff
    show_rolloff_sliders = is_rolloff

    return {
        K.DISTILLED_CFG_END_SLIDER: gr.update(visible=show_final_gs, interactive=show_final_gs),
        K.ROLL_OFF_START_SLIDER: gr.update(visible=show_rolloff_sliders, interactive=show_rolloff_sliders),
        K.ROLL_OFF_FACTOR_SLIDER: gr.update(visible=show_rolloff_sliders, interactive=show_rolloff_sliders),
    }

def wire_events(components: dict):
    """Wires up miscellaneous UI events, like live calculations."""
    logger.info("Wiring misc events...")

    # --- 1. Scheduler Visibility Change ---
    # This event shows/hides the relevant sliders when the CFG schedule shape is changed.
    scheduler_output_keys = [K.DISTILLED_CFG_END_SLIDER, K.ROLL_OFF_START_SLIDER, K.ROLL_OFF_FACTOR_SLIDER]
    scheduler_output_components = [components[k] for k in scheduler_output_keys]
    (components[K.VARIABLE_CFG_SHAPE_RADIO].change(
        fn=handle_scheduler_visibility_change,
        inputs=[components[K.VARIABLE_CFG_SHAPE_RADIO]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=scheduler_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=scheduler_output_components
    ))

    # --- 2. Total Segments Display Update ---
    # This event recalculates the number of segments whenever a relevant slider changes.
    segment_calc_inputs = [
        components[K.VIDEO_LENGTH_SLIDER],
        components[K.FPS_SLIDER]
    ]
    segment_calc_output_keys = [K.TOTAL_SEGMENTS_DISPLAY]
    segment_calc_output_components = [components[k] for k in segment_calc_output_keys]

    for component in segment_calc_inputs:
        (component.change(
            fn=event_handlers.ui_update_total_segments,
            inputs=segment_calc_inputs,
            outputs=[components[K.HANDLER_OUTPUT_STATE]]
        ).then(
            fn=partial(apply_updates, output_keys=segment_calc_output_keys, components_map=components), # ADDED components_map
            inputs=[components[K.HANDLER_OUTPUT_STATE]],
            outputs=segment_calc_output_components
        ))

