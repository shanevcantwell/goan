  # ui/layout.py
# This file defines the Gradio UI layout for the goan application.

import gradio as gr
from gradio_modal import Modal

from .enums import ComponentKey as K
from . import workspace as workspace_manager
from . import queue as queue_manager
from . import shared_state as shared_state_module

def create_ui():
    """
    Creates the Gradio UI layout and returns a dictionary of all UI components.
    """

    css = """
    #queue_df { font-size: 0.9rem; }

    /* --- Task Queue Column Styling --- */
    /* Use a fixed table layout to enforce column widths accurately. */
    #queue_df table {
        table-layout: fixed;
        width: 100%;
    }

    /* Default for all headers/cells: vertical alignment and basic padding. */
    #queue_df th, #queue_df td {
        vertical-align: middle;
        padding: 4px;
    }

        width: 2.0rem; /* Shrink width to give more space to the prompt column */
        text-align: center;
        padding: 0 2px; /* Default padding for headers */
    }
    #queue_df td:nth-child(-n+5) {
        padding: 0; /* Remove padding from cells to let the link fill them entirely */
    }

    /* --- Fix for Queue Action Click Targets --- */
    /* Make the entire cell for an action icon a clickable link, improving hit area. */
    #queue_df td:nth-child(-n+5) a {
        display: block;
        padding: 4px 2px; /* This padding defines the clickable area inside the link. */
        line-height: 1.5; /* Improve vertical spacing and click target height. */
    }
    /* Disable clicks on the disabled action icons (spans) */
    #queue_df td:nth-child(-n+5) span {
        pointer-events: none;
    }
    /* Disable the annoying drag behavior on links and images in the queue */
    #queue_df a, #queue_df img {
        -webkit-user-drag: none; user-drag: none;
        user-select: none; -webkit-user-select: none; -moz-user-select: none;
    }

    /* Status Column (6): Fixed width, left-aligned, allows wrapping. */
    #queue_df th:nth-child(6), #queue_df td:nth-child(6) {
        width: 8rem; /* Wide enough for "⏳ Processing" */
        text-align: left;
        white-space: normal; /* Allow text to wrap */
    }

    /* Prompt Column (7): Flexible width, left-aligned, truncates with ellipsis. */
    #queue_df th:nth-child(7), #queue_df td:nth-child(7) {
        text-align: left;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Image (8), Length (9), ID (10) Columns: Fixed width, centered. */
    #queue_df th:nth-child(8), #queue_df td:nth-child(8) { width: 4rem; text-align: center; }
    #queue_df th:nth-child(9), #queue_df td:nth-child(9) { width: 4rem; text-align: center; }
    #queue_df th:nth-child(10), #queue_df td:nth-child(10) { width: 3rem; text-align: center; }

    .gradio-container { max-width: 95% !important; margin: auto !important; }
    :root {
        --color-accent-soft: #4CAF50; --color-accent-50: #e8f5e9;
        --color-accent-100: #c8e6c9; --color-accent-200: #a5d6a7;
        --color-accent-300: #81c784; --color-accent-400: #66bb6a;
        --color-accent-500: #4CAF50; --color-accent-600: #43A047;
        --color-accent-700: #388E3C; --color-accent-800: #2E7D32;
        --color-accent-900: #1B5E20;
    }
    /* Apply green color only to *enabled* primary buttons to allow default disabled styles. */
    .gr-button-primary:not([disabled]) { background-color: var(--color-accent-500) !important; color: white !important; }
    .gr-button-primary:not([disabled]):hover { background-color: var(--color-accent-600) !important; }

    /* Custom blue color for specific action buttons */
    #clear_image_button:not([disabled]), #download_image_button:not([disabled]) {
        background-color: #3b82f6 !important; /* A softer, less intense blue */
        color: white !important;
        border-color: #3b82f6 !important;
    }
    #clear_image_button:not([disabled]):hover, #download_image_button:not([disabled]):hover {
        background-color: #2563eb !important; /* A slightly darker blue for hover */
    }

    /* --- Consistent Disabled Button Styling --- */
    /* This ensures all buttons, regardless of their original color, have the same greyed-out appearance when disabled. */
    .gr-button-primary[disabled],
    .gr-button-stop[disabled],
    #clear_image_button[disabled],
    #download_image_button[disabled] {
        background-color: #374151 !important; /* Dark grey for dark theme */
        color: #9ca3af !important;            /* Muted grey for text */
        border-color: #4b5563 !important;     /* Slightly lighter border */
    }

    /* Highlight the Image Input Box on Load */
    #image_file_input_ui {
        background-color: var(--color-accent-800); /* A dark green fill */
        border-radius: 5px;
        border: 2px dashed var(--color-accent-200); /* A light green dashed border */
    }
    #image_file_input_ui .text-gray-500 { /* This targets the default text color class */
        color: var(--color-accent-100) !important;
    }

    /* --- NEW, MORE ROBUST FIX for fullscreen images --- */
    /* This targets any image inside a fixed-position container, which is
       how Gradio implements the fullscreen view. Using a space instead of '>'
       makes it work even if the image is nested inside other divs. */
    div.fixed img {
        width: auto !important;
        height: auto !important;
        max-width: 95vw !important;  /* Max width is 95% of the viewport width */
        max-height: 95vh !important; /* Max height is 95% of the viewport height */
        object-fit: contain !important; /* This preserves the aspect ratio */
    }

    #current_task_preview_image_ui div.fixed img {
        max-width: 95vw !important;
        max-height: 50vh !important;
        object-fit: contain !important;
    }
        /* Makes the column a flex container that can stretch vertically */
    .fill-height-column {
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    /* --- NEW: Styling for progress bar and description to fill column width --- */
    /* Target the HTML component for the progress bar */
    #current_task_progress_bar_ui {
        width: 100% !important;
    }

    /* Makes the element containing the prompts grow to fill the available space */
    #current_task_progress_description_ui {
        width: 100% !important;
    }
    /* Ensures the Textbox wrappers inside the container also grow */
    .prompt-container {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    /* Ensures the Textbox wrappers inside the container also grow */
    .prompt-container > .gr-form {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    .prompt-container > .gr-form > .gr-textarea-wrapper {
        flex-grow: 1;
    }
    .total_segments_display > .gr-markdown {
     height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-end; /* Aligns content to the bottom */
    }
    .current_task_progress_bar > .gr-html {
}

    """

    components = {}
    components[K.BLOCK] = gr.Blocks(css=css, title="goan").queue()

    with components[K.BLOCK]:
        # components[K.LAST_COMPLETED_SEED_STATE] = gr.State(-1)
        components[K.APP_STATE] = gr.State({
            "queue_state": {"queue": [], "next_id": 1, "processing": False, "editing_task_id": None},
            "last_completed_video_path": None,
            "lora_state": {"loaded_loras": {}}
        })
        components[K.LORA_NAME_STATE] = gr.Textbox(visible=False, label="LoRA Names State")
        components[K.EXTRACTED_METADATA_STATE] = gr.State({})
        # components[K.RESUME_LATENT_PATH_STATE] = gr.State(None)
        components[K.METADATA_MODAL_TRIGGER_STATE] = gr.Textbox(visible=False)
        # New: State component to capture the output of the preview action
        # components[K.PREVIEW_ACTION_OUTPUT_STATE] = gr.State(None)

        gr.Markdown('# goan (Powered by FramePack)')

        with Modal(visible=False) as metadata_modal:
            components[K.METADATA_MODAL] = metadata_modal
            gr.Markdown("Image has saved parameters. Overwrite current creative settings?")
            components[K.METADATA_PROMPT_PREVIEW] = gr.Textbox(label="Detected Prompt", interactive=False, lines=5, max_lines=10)
            components[K.METADATA_OVERWRITE_SEED_CHECKBOX] = gr.Checkbox(label="Overwrite current seed with metadata seed", value=True, scale=1)
            with gr.Row():
                components[K.CANCEL_METADATA_BUTTON] = gr.Button("No")
                components[K.CONFIRM_METADATA_BUTTON] = gr.Button("Yes, Apply", variant="primary")

        with gr.Row():
            with gr.Column(scale=1):
                components[K.IMAGE_FILE_INPUT] = gr.File(label="Drop Final Image for I2V", file_types=["image"], elem_id="image_file_input_ui")
                components[K.INPUT_IMAGE_DISPLAY] = gr.Image(type="pil", label="Current Input Image", interactive=False, visible=False, height=220, show_download_button=False)
                components[K.CANCEL_EDIT_TASK_BUTTON] = gr.Button("Cancel Edit", visible=False, variant="secondary", size="sm")
                components[K.CLEAR_IMAGE_BUTTON] = gr.Button("Replace Image", variant="secondary", interactive=False, elem_id="clear_image_button", scale=1)
                components[K.DOWNLOAD_IMAGE_BUTTON] = gr.Button("Download Image with Parameters", variant="secondary", interactive=False, elem_id="download_image_button", scale=1) # I just can't think of a way to express the concept in 4ish words
            with gr.Column(scale=2, min_width=600):
                components[K.POSITIVE_PROMPT] = gr.Textbox(label="Prompt", lines=11, elem_id="positive_prompt")
                components[K.NEGATIVE_PROMPT] = gr.Textbox(label="Negative Prompt", lines= 6,elem_id="negative_prompt")
                components[K.VIDEO_LENGTH_SLIDER] = gr.Slider(label="Video Length (s)", minimum=0.1, maximum=120, value=5.0, step=0.1)
        with gr.Group():
            # These hidden file components are the targets for one-click downloads.
            components[K.IMAGE_DOWNLOADER] = gr.File(visible=False, elem_id="image_downloader_hidden_file")
            components[K.QUEUE_DOWNLOADER] = gr.File(visible=False, elem_id="queue_downloader_hidden_file")
        with gr.Row():
            with gr.Column(scale=1):
                components[K.ADD_TASK_BUTTON] = gr.Button("Add to Queue", variant="secondary", interactive=False)
            with gr.Column(scale=2):
                components[K.PROCESS_QUEUE_BUTTON] = gr.Button("▶️ Process Queue", variant="primary", interactive=False)

        components[K.QUEUE_DF] = gr.DataFrame(
            headers=["", "", "", "", "", "Status", "Prompt", "Image", "Length", "ID"],
            datatype=["markdown", "markdown", "markdown", "markdown", "markdown", "markdown", "markdown", "markdown", "str", "number"],
            col_count=(10, "dynamic"),
            interactive=True,
            elem_id="queue_df",
            max_height=350
        )
        with gr.Row():
            components[K.SAVE_QUEUE_BUTTON] = gr.Button("Save Queue", size="sm", interactive=False)
            components[K.LOAD_QUEUE_BUTTON] = gr.UploadButton("Load Queue", file_types=[".zip"], size="sm", variant="primary")
            components[K.CLEAR_QUEUE_BUTTON] = gr.Button("Clear Pending", size="sm", variant="stop", interactive=False)

        components[K.CURRENT_TASK_PREVIEW_IMAGE] = gr.Image(
            # label="Live Latent Preview",
            interactive=False,
            # visible=False, # Starts hidden, made visible by the agent during processing.
            visible=False,
            show_download_button=False,
            elem_id="current_task_preview_image_ui"
        )

        # with gr.Row():
        #     with gr.Column(scale=1):
        #         components[K.CURRENT_TASK_PROGRESS_BAR] = gr.HTML('', elem_id="current_task_progress_bar")
        #     with gr.Column(scale=2):
        #         components[K.CURRENT_TASK_PROGRESS_DESCRIPTION] = gr.Markdown('', elem_id="current_task_progress_description_ui")

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Accordion("Advanced Settings", open=False):
                    with gr.Row():
                        with gr.Column(scale=2):
                            components[K.SEED] = gr.Number(label="Seed", value=-1, precision=0, minimum=-1, maximum=2**32 - 1)
                        # with gr.Column(scale=1):
                        #     with gr.Row():
                        #         components[K.RANDOM_SEED_BUTTON] = gr.Button("🎲", elem_classes=["icon-button"], scale=1)
                        #         components[K.REUSE_SEED_BUTTON] = gr.Button("♻️", elem_classes=["icon-button"], scale=1)
                    components[K.VARIABLE_CFG_SHAPE_RADIO] = gr.Radio(["Off", "Linear", "Roll-off"], label="Variable CFG", value="Off")
                    with gr.Row():
                        components[K.ROLL_OFF_START_SLIDER] = gr.Slider(label="Roll-off Start %", minimum=0, maximum=100, value=75, step=1, visible=False)
                        components[K.ROLL_OFF_FACTOR_SLIDER] = gr.Slider(label="Roll-off Curve Factor", minimum=0.25, maximum=4.0, value=1.0, step=0.05, visible=False)
                    with gr.Row():
                        components[K.DISTILLED_CFG_START_SLIDER] = gr.Slider(label="Distilled CFG Start", minimum=1.0, maximum=32.0, value=10.0, step=0.01)
                        components[K.DISTILLED_CFG_END_SLIDER] = gr.Slider(label="Distilled CFG End", minimum=1.0, maximum=32.0, value=10.0, step=0.01, interactive=False)
                    with gr.Row():
                        components[K.REAL_CFG_SLIDER] = gr.Slider(label="CFG (Real)", minimum=1.0, maximum=8.0, value=1.5, step=0.01)
                        components[K.STEPS_SLIDER] = gr.Slider(label="Steps", minimum=1, maximum=100, value=25, step=1)
                    components[K.GUIDANCE_RESCALE_SLIDER] = gr.Slider(label="RS", minimum=0.0, maximum=32.0, value=0.0, step=0.01, visible=False)

                with gr.Accordion("LoRA Settings", open=False, visible=True) as lora_accordion:
                    components[K.LORA_ACCORDION] = lora_accordion
                    gr.Markdown(
                        "🧪 **Experimental LoRA Support**\n\n"
                        "Upload a `.safetensors` file to apply it before generation. "
                        "Note that compatibility with 'wild' LoRAs can vary, and some may not affect the output as expected."
                    )
                    components[K.LORA_UPLOAD_BUTTON] = gr.UploadButton("Upload LoRA", file_types=[".safetensors"], file_count="single", size="sm")
                    with gr.Row(visible=False, variant="panel") as lora_row_0_ctx:
                        components[K.LORA_ROW] = lora_row_0_ctx
                        components[K.LORA_NAME] = gr.Textbox(label="LoRA Name", interactive=False, scale=2)
                        components[K.LORA_WEIGHT] = gr.Slider(label="Weight", minimum=-2.0, maximum=2.0, step=0.05, value=1.0, scale=3)
                        components[K.LORA_TARGETS] = gr.CheckboxGroup(label="Target Models", choices=["transformer", "text_encoder", "text_encoder_2"], value=["text_encoder"], scale=3)

                with gr.Accordion("Debug Settings", open=False):
                    components[K.USE_TEACACHE_CHECKBOX] = gr.Checkbox(label='Use TeaCache', value=True)
                    # Hide the FP32 checkbox on legacy GPUs, as it's forced on in the backend.
                    is_legacy_gpu = shared_state_module.shared_state_instance.system_info.get('is_legacy_gpu', False)
                    components[K.USE_FP32_TRANSFORMER_OUTPUT_CHECKBOX] = gr.Checkbox(
                        label="Use FP32 Transformer Output",
                        value=False,
                        visible=not is_legacy_gpu,
                        info="Forces the final output of the transformer to full precision. May improve quality at the cost of performance. Does not affect the VAE."
                    )
                    components[K.GPU_MEMORY_PRESERVATION_SLIDER] = gr.Slider(label="GPU Preserved (GB)", minimum=4, maximum=128, value=6.0, step=0.1)
                    components[K.FPS_SLIDER] = gr.Slider(label="MP4 Framerate (FPS)", minimum=1, maximum=60, value=30, step=1)
                    components[K.MP4_CRF_SLIDER] = gr.Slider(label="MP4 CRF", minimum=0, maximum=51, value=18, step=1)
                    components[K.LATENT_WINDOW_SIZE_SLIDER] = gr.Slider(label="Latent Window Size", minimum=1, maximum=33, value=9, step=1, visible=False)
                    components[K.OUTPUT_FOLDER_TEXTBOX] = gr.Textbox(label="Output Folder", value=workspace_manager.outputs_folder)
                    components[K.SAVE_AS_DEFAULT_BUTTON] = gr.Button("Save as Default", variant="secondary")
                    components[K.RELAUNCH_NOTIFICATION_MD] = gr.Markdown("ℹ️ **Restart required** for new output path to take effect.", visible=False)
            with gr.Column(scale=2):
                with gr.Row(equal_height=True):
                    components[K.CREATE_PREVIEW_BUTTON] = gr.Button("📸 Generate a preview for the currently processing segment", variant="secondary", interactive=False, visible=False, elem_id="create_preview_button")
                    components[K.CURRENT_TASK_PROGRESS_BAR] = gr.HTML('', elem_id="current_task_progress_bar")
                with gr.Row(equal_height=True):
                    components[K.TOTAL_SEGMENTS_DISPLAY] = gr.Markdown("Calculated Total Segments: N/A", elem_id="total_segments_display")
                    components[K.CURRENT_TASK_PROGRESS_DESCRIPTION] = gr.Markdown('', elem_id="current_task_progress_description_ui")
                with gr.Row(equal_height=True):
                    components[K.PREVIEW_FREQUENCY_SLIDER] = gr.Slider(label="Interval of periodic automatic previews", minimum=0, maximum=100, value=5, step=1)
                    components[K.PREVIEW_SPECIFIED_SEGMENTS_TEXTBOX] = gr.Textbox(label="Comma-separated specific segments to preview", value="")
                components[K.LAST_FINISHED_VIDEO] = gr.Video(interactive=True, autoplay=False, height=540)

    return components