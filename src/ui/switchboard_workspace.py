import logging
from functools import partial

from .enums import ComponentKey as K
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
