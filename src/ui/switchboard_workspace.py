import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import event_handlers
from . import workspace as workspace_manager
from . import shared_state as shared_state_module
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires up the workspace save/load events."""
    logger.info("Wiring workspace events...")

    # Use the list from shared_state as the single source of truth for the order of UI components.
    full_workspace_ui_components = [components[key] for key in shared_state_module.ALL_TASK_UI_KEYS]

    # Define the output keys for the save action.
    save_default_output_keys = [K.RELAUNCH_NOTIFICATION_MD]
    save_default_output_components = [components[k] for k in save_default_output_keys]

    (components[K.SAVE_AS_DEFAULT_WORKSPACE_BUTTON].click(
        fn=workspace_manager.save_as_default_workspace,
        inputs=full_workspace_ui_components,
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
    ).then(
        fn=partial(apply_updates, output_keys=save_default_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=save_default_output_components,
    ))

    # --- Wire Variable CFG UI ---
    # This logic controls the visibility and state of sliders related to Variable CFG.
    # It's triggered by changes to either the shape radio or the start CFG slider.
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

    def wire_variable_cfg_update(trigger_component):
        (trigger_component.change(
            fn=event_handlers.update_variable_cfg_controls_visibility,
            inputs=variable_cfg_input_components,
            outputs=[components[K.HANDLER_OUTPUT_STATE]]
        ).then(
            fn=partial(apply_updates, output_keys=variable_cfg_output_keys, components_map=components),
            inputs=[components[K.HANDLER_OUTPUT_STATE]],
            outputs=variable_cfg_output_components
        ))

    wire_variable_cfg_update(components[K.VARIABLE_CFG_SHAPE_RADIO])
    wire_variable_cfg_update(components[K.DISTILLED_CFG_START_SLIDER])
