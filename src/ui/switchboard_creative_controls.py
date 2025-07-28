import logging
from functools import partial
import gradio as gr

from .enums import ComponentKey as K
from .switchboard_helpers import apply_updates
from . import event_handler_helpers as helpers

logger = logging.getLogger(__name__)    
                         
def wire_events(components: dict):
    """Wires up interactive events for the main creative UI controls."""
    logger.info("Wiring creative control events...")

    # --- Wire Variable CFG UI ---
    variable_cfg_input_keys = [
        K.VARIABLE_CFG_SHAPE_RADIO,
        K.DISTILLED_CFG_START_SLIDER
    ]
    variable_cfg_input_components = [components[k] for k in variable_cfg_input_keys]

    variable_cfg_output_keys = [
        K.DISTILLED_CFG_END_SLIDER,
        K.ROLL_OFF_START_SLIDER,
        K.ROLL_OFF_FACTOR_SLIDER
    ]
    variable_cfg_output_components = [components[k] for k in variable_cfg_output_keys]

    # Wire the radio button change event directly.
    (components[K.VARIABLE_CFG_SHAPE_RADIO].change(
        fn=helpers.update_variable_cfg_controls_visibility,
        inputs=variable_cfg_input_components,
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=variable_cfg_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=variable_cfg_output_components
    ))

    # Wire the start slider change event directly.
    (components[K.DISTILLED_CFG_START_SLIDER].change(
        fn=helpers.update_variable_cfg_controls_visibility,
        inputs=variable_cfg_input_components,
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=variable_cfg_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=variable_cfg_output_components
    ))

    # --- Wire Total Segments Calculation ---
    # This was previously unwired and is now fixed.
    segment_calc_inputs = [
        components[K.VIDEO_LENGTH_SLIDER],
        components[K.FPS_SLIDER]
    ]
    segment_calc_output_keys = [K.TOTAL_SEGMENTS_DISPLAY]
    segment_calc_output_components = [components[k] for k in segment_calc_output_keys]

    for component in segment_calc_inputs:
        (component.change(
            fn=helpers.ui_update_total_segments,
            inputs=segment_calc_inputs,
            outputs=[components[K.HANDLER_OUTPUT_STATE]]
        ).then(
            fn=partial(apply_updates, output_keys=segment_calc_output_keys, components_map=components),
            inputs=[components[K.HANDLER_OUTPUT_STATE]],
            outputs=segment_calc_output_components
        ))

    # --- Wire Settings Menu ---
    # This ensures only one of the settings panels (Power User, LoRA, Advanced) is visible at a time.
    settings_menu_output_keys = [
        K.POWER_USER_GROUP,
        K.LORA_GROUP,
        K.ADVANCED_SETTINGS_GROUP,
    ]
    settings_menu_output_components = [components[k] for k in settings_menu_output_keys]

    (components[K.SETTINGS_MENU_RADIO].change(
        fn=helpers.handle_settings_menu_change,
        inputs=[components[K.SETTINGS_MENU_RADIO]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=settings_menu_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=settings_menu_output_components
    ))