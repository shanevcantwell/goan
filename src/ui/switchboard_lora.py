import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import lora as lora_manager
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires up the LoRA management UI events."""
    logger.info("Wiring LoRA events...")

    # Define the list of OUTPUT KEYS for the event. This is the single source of truth.
    lora_upload_output_keys = [
        K.APP_STATE,
        K.LORA_NAME_STATE,
        K.LORA_ROW,
        K.LORA_NAME,
        K.LORA_WEIGHT,
        K.LORA_TARGETS,
    ]
    # Map the keys to the actual Gradio components.
    lora_upload_output_components = [components[k] for k in lora_upload_output_keys]

    (components[K.LORA_UPLOAD_BUTTON].upload(
        fn=lora_manager.handle_lora_upload_and_update_ui,
        inputs=[components[K.APP_STATE], components[K.LORA_UPLOAD_BUTTON]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
    ).then(
        fn=partial(apply_updates, output_keys=lora_upload_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=lora_upload_output_components
    ))

