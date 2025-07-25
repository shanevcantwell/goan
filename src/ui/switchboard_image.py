import gradio as gr
import logging
from functools import partial

from .enums import ComponentKey as K
from . import (
    metadata as metadata_manager,
    event_handler_helpers, event_handlers,
    shared_state as shared_state_module
)
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires up the main image input and metadata modal events."""
    logger.info("Wiring image and metadata events...")

    # --- 1. Image Upload Event ---
    # This event consolidates file drop, metadata extraction, and button state updates.
    upload_output_keys = (
        [
            K.IMAGE_FILE_INPUT, K.INPUT_IMAGE_DISPLAY, K.METADATA_PROMPT_PREVIEW,
            K.EXTRACTED_METADATA_STATE, K.METADATA_MODAL_TRIGGER_STATE,
        ] +
        shared_state_module.CREATIVE_UI_KEYS +
        event_handler_helpers.BUTTON_KEYS
    )
    upload_output_components = [components[k] for k in upload_output_keys]

    # NOTE: This requires a new consolidated handler, `handle_image_upload`, to be created
    # in `event_handlers.py` that combines the logic of `workspace.handle_file_drop`
    # and `event_handler_helpers.update_button_states`.
    (components[K.IMAGE_FILE_INPUT].upload(
        fn=event_handlers.handle_image_upload,
        inputs=[components[K.IMAGE_FILE_INPUT]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=upload_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=upload_output_components
    ))

    # --- 2. Clear Image Event ---
    # This event consolidates clearing the image and updating button states.
    clear_output_keys = (
        [
            K.IMAGE_FILE_INPUT, K.INPUT_IMAGE_DISPLAY, K.EXTRACTED_METADATA_STATE
        ] +
        event_handler_helpers.BUTTON_KEYS
    )
    clear_output_components = [components[k] for k in clear_output_keys]

    # NOTE: This requires a new consolidated handler, `handle_clear_image`, to be created
    # in `event_handlers.py` that combines `event_handlers.clear_image_action` and
    # `event_handler_helpers.update_button_states` and returns a dictionary.
    (components[K.CLEAR_IMAGE_BUTTON].click(
        fn=event_handlers.handle_clear_image,
        inputs=None,
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=clear_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=clear_output_components
    ))

    # --- 3. Download Image Event ---
    # This uses a JS-based download trigger, which is a standard Gradio pattern.
    # The inputs must be ordered to exactly match the signature of event_handlers.prepare_image_for_download
    # which is: (pil_image, lora_name, lora_weight, lora_targets, *creative_values)
    lora_ui_inputs = [
        components[K.LORA_NAME],
        components[K.LORA_WEIGHT],
        components[K.LORA_TARGETS]
    ]
    creative_ui_inputs = [components[key] for key in shared_state_module.CREATIVE_UI_KEYS]
    download_handler_inputs = [components[K.INPUT_IMAGE_DISPLAY]] + lora_ui_inputs + creative_ui_inputs

    (components[K.DOWNLOAD_IMAGE_BUTTON].click(
        fn=event_handlers.prepare_image_for_download,
        inputs=download_handler_inputs,
        outputs=components[K.IMAGE_DOWNLOADER], show_progress=True, api_name="download_image_with_metadata"
    ).then(
        fn=None, inputs=None, outputs=None,
        js="(file) => { document.getElementById('image_downloader_hidden_file').querySelector('a[download]').click(); }"
    ))

    # --- 4. Metadata Modal Events ---
    # a. Trigger modal visibility
    components[K.METADATA_MODAL_TRIGGER_STATE].change(
        fn=lambda x: gr.update(visible=True) if x else gr.update(visible=False),
        inputs=[components[K.METADATA_MODAL_TRIGGER_STATE]],
        outputs=[components[K.METADATA_MODAL]],
        api_name=False, queue=False
    )

    # b. Confirm Metadata Button
    # This event consolidates preprocessing, applying metadata, recalculating segments, and closing the modal.
    confirm_metadata_output_keys = (
        shared_state_module.CREATIVE_UI_KEYS +
        [K.TOTAL_SEGMENTS_DISPLAY, K.METADATA_MODAL_TRIGGER_STATE]
    )
    confirm_metadata_output_components = [components[k] for k in confirm_metadata_output_keys]

    # NOTE: This requires a new consolidated handler, `handle_confirm_metadata`, to be created
    # in `event_handlers.py` that combines the logic from the old .then() chain.
    (components[K.CONFIRM_METADATA_BUTTON].click(
        fn=event_handlers.handle_confirm_metadata,
        inputs=[
            components[K.EXTRACTED_METADATA_STATE],
            components[K.VIDEO_LENGTH_SLIDER], components[K.FPS_SLIDER]
        ],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=confirm_metadata_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=confirm_metadata_output_components
    ))

    # c. Cancel Metadata Button
    components[K.CANCEL_METADATA_BUTTON].click(fn=lambda: gr.update(value=None), inputs=None, outputs=[components[K.METADATA_MODAL_TRIGGER_STATE]])
