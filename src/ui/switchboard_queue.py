import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import (
    queue as queue_actions,
    queue_processing,
    event_handler_helpers, event_handler_helpers, event_handlers,
    shared_state as shared_state_module,
)
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires up all queue management events."""
    logger.info("Wiring queue events...")

    # --- Define Inputs & Outputs ---

    # Inputs for creating/updating a task
    # Add K.INPUT_IMAGE_DISPLAY to the inputs for add_or_update_task_in_queue
    task_defining_ui_inputs = [components[key] for key in shared_state_module.ALL_TASK_UI_KEYS]
    add_task_inputs = [components[K.INPUT_IMAGE_DISPLAY]] + task_defining_ui_inputs # <-- MODIFIED

    # Inputs for the queue processing generator
    lora_ui_controls = [components[K.LORA_NAME_STATE], components[K.LORA_WEIGHT], components[K.LORA_TARGETS]]

    # Output keys for events that modify a task or the UI state (add, select, cancel edit)
    # These events reset the main UI controls.
    task_modification_output_keys = (
        [K.APP_STATE, K.QUEUE_DF, K.INPUT_IMAGE_DISPLAY, K.IMAGE_FILE_INPUT] +
        shared_state_module.ALL_TASK_UI_KEYS +
        event_handler_helpers.BUTTON_KEYS
    )
    task_modification_output_components = [components[k] for k in task_modification_output_keys]

    # Output keys for clearing the queue
    clear_queue_output_keys = [K.QUEUE_DF] + event_handler_helpers.BUTTON_KEYS
    clear_queue_output_components = [components[k] for k in clear_queue_output_keys]

    # Output keys for loading a queue
    load_queue_output_keys = [K.QUEUE_DF] + event_handler_helpers.BUTTON_KEYS
    load_queue_output_components = [components[k] for k in load_queue_output_keys]

    # Outputs for the queue processing generator (this is a special case, not using the dict pattern)
    # This list must exactly match the number and order of items yielded by queue_processing.process_task_queue_and_listen.
    # The previous list had 12 items, but the generator yields 9, causing a ValueError.
    process_q_outputs = [
        components[K.APP_STATE], # The generator yields a no-op for this, but it holds a place.
        components[K.QUEUE_DF],
        components[K.LAST_FINISHED_VIDEO],
        components[K.CURRENT_TASK_PREVIEW_IMAGE],
        
        # Removed from alpha 0.2 scope - **TODO: can this be refactored out of this hard pipeline implementation?**
        components[K.CURRENT_TASK_PROGRESS_DESCRIPTION],
        components[K.CURRENT_TASK_PROGRESS_BAR],
        
        components[K.PROCESS_QUEUE_BUTTON],
        components[K.CREATE_PREVIEW_BUTTON],
        components[K.CLEAR_QUEUE_BUTTON],
    ]

    # --- Wire Events ---

    # 1. Add Task to Queue
    (components[K.ADD_TASK_BUTTON].click(
        fn=queue_actions.add_or_update_task_in_queue,
        inputs=add_task_inputs, # <-- MODIFIED: Now includes K.INPUT_IMAGE_DISPLAY
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
        api_name="add_task"
    ).then(
        fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=task_modification_output_components
    ))

    # 2. Process Queue (Generator)
    (components[K.PROCESS_QUEUE_BUTTON].click(
        fn=event_handlers.optimistic_process_button_update,
        inputs=None,
        outputs=[components[K.PROCESS_QUEUE_BUTTON]]
    ).then(
        fn=queue_processing.process_task_queue_and_listen,
        inputs=lora_ui_controls,
        outputs=process_q_outputs
    ))

    # 3. Create Manual Preview
    (components[K.CREATE_PREVIEW_BUTTON].click(
        fn=event_handlers.toggle_manual_preview_action,
        inputs=[components[K.INPUT_IMAGE_DISPLAY]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=event_handler_helpers.BUTTON_KEYS, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=event_handler_helpers.get_button_state_outputs(components)
    ))

    # 4. Cancel Edit (if uncommented, ensure it passes input_image_display)
    # (components[K.CANCEL_EDIT_BUTTON].click(
    #     fn=queue_actions.cancel_edit_action,
    #     inputs=[components[K.INPUT_IMAGE_DISPLAY]], # <-- ADD THIS INPUT
    #     outputs=None
    # ).then(
    #     fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components),
    #     inputs=None,
    #     outputs=task_modification_output_components
    # ))

    # 5. Clear Queue
    (components[K.CLEAR_QUEUE_BUTTON].click(
        fn=queue_actions.clear_task_queue_action,
        inputs=[components[K.INPUT_IMAGE_DISPLAY]], # <-- MODIFIED: Pass current image state
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=clear_queue_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=clear_queue_output_components
    ))

    # 6. Save Queue (JS Download)
    # ... (no changes here)

    # 7. Load Queue
    (components[K.LOAD_QUEUE_BUTTON].upload(
        fn=queue_actions.load_queue_from_zip,
        inputs=[components[K.LOAD_QUEUE_BUTTON], components[K.INPUT_IMAGE_DISPLAY]], # <-- MODIFIED: Pass current image state
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=load_queue_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=load_queue_output_components
    ))

    # 8. Select Task in Queue
    (components[K.QUEUE_DF].select(
        fn=queue_actions.handle_queue_action_on_select,
        inputs=[components[K.INPUT_IMAGE_DISPLAY]], # <-- MODIFIED: Pass current image state
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
        show_progress="hidden"
    ).then(
        fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components),
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=task_modification_output_components
    ))
