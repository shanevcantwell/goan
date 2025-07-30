import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import (
    session_manager,
    event_handler_helpers, event_handlers,
    shared_state as shared_state_module,
)
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires events that run on application load and shutdown."""
    logger.info("Wiring app startup and shutdown events...")
    block = components[K.BLOCK]

    # Define the list of output keys for the startup event.
    startup_output_keys = (
        shared_state_module.ALL_TASK_UI_KEYS +
        [
            K.INPUT_IMAGE_DISPLAY, K.CLEAR_IMAGE_BUTTON, K.DOWNLOAD_IMAGE_BUTTON, K.IMAGE_FILE_INPUT
        ] +
        event_handler_helpers.BUTTON_KEYS
    )
    startup_output_components = [components[key] for key in startup_output_keys]

    # On startup, the handler returns a dictionary of all UI updates.
    # The .then() block uses the apply_updates helper to map this dictionary
    # to the correct list of output components.
    (block.load(
        fn=session_manager.load_and_apply_workspace_on_start,
        inputs=None,
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=startup_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=startup_output_components
    ))

    # Wire shutdown event
    shutdown_inputs = [components[K.INPUT_IMAGE_DISPLAY]] + [components[key] for key in shared_state_module.ALL_TASK_UI_KEYS]
    # components[K.SHUTDOWN_BUTTON].click(fn=event_handlers.safe_shutdown_action, inputs=[components[K.APP_STATE]] + shutdown_inputs, outputs=None, visible=False)
