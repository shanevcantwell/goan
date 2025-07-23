import logging
from functools import partial

import gradio as gr
from .enums import ComponentKey as K
from . import (
    queue as queue_actions,
    queue_processing,
    event_handlers,
    shared_state as shared_state_module,
)
from .switchboard_helpers import apply_updates

logger = logging.getLogger(__name__)

def wire_events(components: dict):
    """Wires up all queue management events."""
    logger.info("Wiring queue events...")
    
    # --- Define Inputs & Outputs ---

    # Inputs for creating/updating a task
    task_defining_ui_inputs = [components[key] for key in shared_state_module.ALL_TASK_UI_KEYS]
    add_task_inputs = [components[K.INPUT_IMAGE_DISPLAY]] + task_defining_ui_inputs

    # Inputs for the queue processing generator
    lora_ui_controls = [components[K.LORA_NAME_STATE], components[K.LORA_WEIGHT], components[K.LORA_TARGETS]]

    # Output keys for events that modify a task or the UI state (add, select, cancel edit)
    # These events reset the main UI controls.
    task_modification_output_keys = (
        [K.APP_STATE, K.QUEUE_DF, K.INPUT_IMAGE_DISPLAY, K.IMAGE_FILE_INPUT] +
        shared_state_module.ALL_TASK_UI_KEYS +
        event_handlers.BUTTON_KEYS
    )
    task_modification_output_components = [components[k] for k in task_modification_output_keys]

    # Output keys for clearing the queue
    clear_queue_output_keys = [K.QUEUE_DF] + event_handlers.BUTTON_KEYS
    clear_queue_output_components = [components[k] for k in clear_queue_output_keys]

    # Output keys for loading a queue
    load_queue_output_keys = [K.QUEUE_DF] + event_handlers.BUTTON_KEYS
    load_queue_output_components = [components[k] for k in load_queue_output_keys]

    # Outputs for the queue processing generator (this is a special case, not using the dict pattern)
    process_q_outputs = [
        components[K.QUEUE_DF], components[K.LAST_FINISHED_VIDEO],
        components[K.CURRENT_TASK_PREVIEW_IMAGE], components[K.CURRENT_TASK_PROGRESS_DESCRIPTION],
        components[K.CURRENT_TASK_PROGRESS_BAR]
    ] + event_handlers.get_button_state_outputs(components) # Buttons are updated directly by the generator

    # --- Wire Events ---

    # 1. Add Task to Queue
    # NOTE: Assumes `add_or_update_task_in_queue` returns a dictionary.
    (components[K.ADD_TASK_BUTTON].click(
        fn=queue_actions.add_or_update_task_in_queue,
        inputs=add_task_inputs,
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
        api_name="add_task"
    ).then(
        fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=task_modification_output_components
    ))

    # 2. Process Queue (Generator)
    # This event uses a generator and is a special case. The .then() chain is correct here.
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
    # NOTE: Assumes `toggle_manual_preview_action` is updated to return a dictionary of button states.
    (components[K.CREATE_PREVIEW_BUTTON].click(
        fn=event_handlers.toggle_manual_preview_action,
        inputs=[components[K.INPUT_IMAGE_DISPLAY]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=event_handlers.BUTTON_KEYS, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=event_handlers.get_button_state_outputs(components)
    ))

    # 4. Cancel Edit
    # NOTE: Assumes `cancel_edit_action` is updated to return a dictionary.
    # (components[K.CANCEL_EDIT_BUTTON].click(
    #     fn=queue_actions.cancel_edit_action,
    #     inputs=None,
    #     outputs=None
    # ).then(
    #     fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components), # ADDED components_map
    #     inputs=None,
    #     outputs=task_modification_output_components
    # ))

    # 5. Clear Queue
    # NOTE: Assumes `clear_queue_action` is updated to return a dictionary.
    (components[K.CLEAR_QUEUE_BUTTON].click(
        fn=queue_actions.clear_task_queue_action,
        inputs=None,
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=clear_queue_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=clear_queue_output_components
    ))

    # 6. Save Queue (JS Download)
    # This event uses a JS-based download and is a special case.
    (components[K.SAVE_QUEUE_BUTTON].click(
        fn=queue_actions.save_queue_to_zip,
        inputs=None,
        outputs=[components[K.QUEUE_DOWNLOADER]],
        show_progress=True
    ).then(
        fn=None, inputs=None, outputs=None,
        js="() => { document.getElementById('queue_downloader_hidden_file').querySelector('a[download]').click(); }"
    ))

    # 7. Load Queue
    # NOTE: Assumes `load_queue_from_zip` is updated to return a dictionary.
    (components[K.LOAD_QUEUE_BUTTON].upload(
        fn=queue_actions.load_queue_from_zip,
        inputs=[components[K.LOAD_QUEUE_BUTTON]],
        outputs=[components[K.HANDLER_OUTPUT_STATE]]
    ).then(
        fn=partial(apply_updates, output_keys=load_queue_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=load_queue_output_components
    ))

    # 8. Select Task in Queue
    # NOTE: Assumes `handle_queue_action_on_select` returns a dictionary.
    (components[K.QUEUE_DF].select(
        fn=queue_actions.handle_queue_action_on_select,
        inputs=None, # The select event itself provides the necessary data (gr.SelectData)
        outputs=[components[K.HANDLER_OUTPUT_STATE]],
        show_progress="hidden"
    ).then(
        fn=partial(apply_updates, output_keys=task_modification_output_keys, components_map=components), # ADDED components_map
        inputs=[components[K.HANDLER_OUTPUT_STATE]],
        outputs=task_modification_output_components
    ))
