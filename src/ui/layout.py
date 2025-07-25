# ui/layout.py
# This file defines the Gradio UI layout for the goan application.

import gradio as gr
from gradio_modal import Modal
from .css_main import APP_CSS

from .enums import ComponentKey as K
from .settings_manager import settings_manager_instance
from . import shared_state as shared_state_module

def create_ui():
    """
    Creates the Gradio UI layout and returns a dictionary of all UI components.
    """

    components = {}
    components[K.BLOCK] = gr.Blocks(css=APP_CSS, title="goan").queue()

    with components[K.BLOCK]:
        # components[K.LAST_COMPLETED_SEED_STATE] = gr.State(-1)
        components[K.APP_STATE] = gr.State({
            "queue_state": {"queue": [], "next_id": 1, "processing": False, "editing_task_id": None},
            "last_completed_video_path": None,
            "lora_state": {"loaded_loras": {}}
        })
        components[K.LORA_NAME_STATE] = gr.Textbox(visible=False, label="LoRA Names State")
        components[K.EXTRACTED_METADATA_STATE] = gr.State({})
        components[K.HANDLER_OUTPUT_STATE] = gr.State({})
        # components[K.RESUME_LATENT_PATH_STATE] = gr.State(None)
        components[K.METADATA_MODAL_TRIGGER_STATE] = gr.Textbox(visible=False)
        # New: State component to capture the output of the preview action
        # components[K.PREVIEW_ACTION_OUTPUT_STATE] = gr.State(None)

        gr.Markdown('# goan (Powered by FramePack)')

        with Modal(visible=False) as metadata_modal:
            components[K.METADATA_MODAL] = metadata_modal
            gr.Markdown("Image has saved parameters. Overwrite current creative settings?")
            components[K.METADATA_PROMPT_PREVIEW] = gr.Textbox(label="Detected Prompt", interactive=False, lines=5, max_lines=10)
            # components[K.METADATA_OVERWRITE_SEED_CHECKBOX] = gr.Checkbox(label="Overwrite current seed with metadata seed", value=True, scale=1)
            with gr.Row():
                components[K.CANCEL_METADATA_BUTTON] = gr.Button("No")
                components[K.CONFIRM_METADATA_BUTTON] = gr.Button("Yes, Apply", variant="primary")

        with gr.Group(elem_classes="top-section-container"):
            with gr.Row():
                with gr.Column(scale=1):
                    components[K.IMAGE_FILE_INPUT] = gr.File(label="Drop Final Image for I2V", file_types=["image"], elem_id="image_file_input_ui")
                    components[K.INPUT_IMAGE_DISPLAY] = gr.Image(type="pil", label="Current Input Image", interactive=False, visible=False, height=220, show_download_button=False, elem_id="input_image_display_ui")
                    # components[K.CANCEL_EDIT_TASK_BUTTON] = gr.Button("Cancel Edit", visible=False, variant="secondary", size="sm")
                    components[K.CLEAR_IMAGE_BUTTON] = gr.Button("Replace Image", interactive=False, elem_id="clear_image_button", scale=1)
                    components[K.DOWNLOAD_IMAGE_BUTTON] = gr.Button("Download Image with Parameters", interactive=False, elem_id="download_image_button", scale=1) # I just can't think of a way to express the concept in 4ish words
                    components[K.VIDEO_LENGTH_SLIDER] = gr.Slider(label="Video Length (s)", minimum=0.1, maximum=120, value=5.0, step=0.1)
                    components[K.ADD_TASK_BUTTON] = gr.Button("Add to Queue", variant="secondary", interactive=False)
                with gr.Column(scale=2, min_width=600):
                    components[K.POSITIVE_PROMPT] = gr.Textbox(label="Prompt", lines=11, max_lines=11, elem_id="positive_prompt")
                    components[K.NEGATIVE_PROMPT] = gr.Textbox(label="Negative Prompt", lines=4, max_lines=4, elem_id="negative_prompt")

        with gr.Group():
            # These hidden file components are the targets for one-click downloads.
            components[K.IMAGE_DOWNLOADER] = gr.File(visible=False, elem_id="image_downloader_hidden_file")
            components[K.QUEUE_DOWNLOADER] = gr.File(visible=False, elem_id="queue_downloader_hidden_file")

        with gr.Row(elem_classes="button-group"):
            components[K.SAVE_QUEUE_BUTTON] = gr.Button("Save Queue", size="sm", interactive=False)
            components[K.LOAD_QUEUE_BUTTON] = gr.UploadButton("Load Queue", file_types=[".zip"], size="sm", variant="primary")
            components[K.CLEAR_QUEUE_BUTTON] = gr.Button("Clear Pending", size="sm", variant="stop", interactive=False)
        components[K.QUEUE_DF] = gr.DataFrame(
            headers=["Status", "Prompt", "Image", "Length (s)", "ID"],
            datatype=["markdown", "markdown", "markdown", "number", "number"],
            elem_id="queue_df",
            max_height=350,
            interactive=False # The grid itself is not interactive; actions are driven by .select()
        )
        with gr.Row():
            with gr.Row(visible=False, equal_height=True) as progress_row:
                components[K.PROGRESS_ROW] = progress_row
                with gr.Column(scale=1):
                    components[K.CURRENT_TASK_PREVIEW_IMAGE] = gr.Image(
                        label="",
                        interactive=False,
                        visible=False, # Starts hidden, made visible by the agent during processing.
                        show_download_button=False,
                        elem_id="current_task_preview_image_ui",
                    )
                with gr.Column(scale=1):
                    gr.Markdown("##### Task Progress")
                    components[K.CURRENT_TASK_PROGRESS_BAR] = gr.HTML('', elem_id="current_task_progress_bar_ui")
                    components[K.CURRENT_TASK_PROGRESS_DESCRIPTION] = gr.Markdown('', elem_id="current_task_progress_description_ui")
                with gr.Column(scale=1):
                    gr.Markdown("##### Segment Progress")
                    components[K.SEGMENT_PROGRESS_BAR] = gr.HTML('', elem_id="segment_progress_bar_ui")
                    components[K.SEGMENT_ETA_DISPLAY] = gr.Markdown('', elem_id="segment_eta_display_ui")
            with gr.Column(scale=1):
                with gr.Accordion("Power User Settings", open=False):
                    with gr.Row():
                        with gr.Column(scale=2):
                            components[K.SEED] = gr.Number(label="Seed", value=-1, precision=0, minimum=-1, maximum=2**32 - 1)
                        # with gr.Column(scale=1):
                        #     with gr.Row():
                        #         components[K.RANDOM_SEED_BUTTON] = gr.Button("🎲", elem_classes=["icon-button"], scale=1)
                        #         components[K.REUSE_SEED_BUTTON] = gr.Button("♻️", elem_classes=["icon-button"], scale=1)
                    components[K.VARIABLE_CFG_SHAPE_RADIO] = gr.Radio(["Off", "Linear", "Roll-off"], label="Variable CFG", value="Off")
                    with gr.Row():
                        components[K.DISTILLED_CFG_START_SLIDER] = gr.Slider(label="Distilled CFG Start", minimum=1.0, maximum=32.0, value=10.0, step=0.01)
                        components[K.DISTILLED_CFG_END_SLIDER] = gr.Slider(label="Distilled CFG End", minimum=1.0, maximum=32.0, value=10.0, step=0.01, interactive=False, visible=False)
                    with gr.Row():
                        components[K.ROLL_OFF_START_SLIDER] = gr.Slider(label="Roll-off Start %", minimum=0, maximum=100, value=75, step=1, visible=False)
                        components[K.ROLL_OFF_FACTOR_SLIDER] = gr.Slider(label="Roll-off Curve Factor", minimum=0.25, maximum=4.0, value=1.0, step=0.05, visible=False)
                    with gr.Row():
                        components[K.REAL_CFG_SLIDER] = gr.Slider(label="CFG (Real)", minimum=1.0, maximum=8.0, value=1.5, step=0.01)
                        components[K.STEPS_SLIDER] = gr.Slider(label="Steps", minimum=1, maximum=100, value=25, step=1)
                    components[K.GUIDANCE_RESCALE_SLIDER] = gr.Slider(label="RS", minimum=0.0, maximum=32.0, value=0.0, step=0.01, visible=False)

                with gr.Accordion("LoRA Settings", open=False) as lora_accordion:
                    components[K.LORA_ACCORDION] = lora_accordion
                    gr.Markdown(
                        "🧪 **Experimental LoRA Support**\n\n"
                        "Upload a `.safetensors` file to apply it before generation."
                        "Note that compatibility with 'wild' LoRAs can vary, and some may not affect the output as expected."
                    )
                    components[K.LORA_UPLOAD_BUTTON] = gr.UploadButton("Upload LoRA", file_types=[".safetensors"], file_count="single", size="sm")
                    with gr.Row(visible=False, variant="panel") as lora_row_0_ctx:
                        components[K.LORA_ROW] = lora_row_0_ctx
                        components[K.LORA_NAME] = gr.Textbox(label="LoRA Name", interactive=False, scale=2)
                        components[K.LORA_WEIGHT] = gr.Slider(label="Weight", minimum=-2.0, maximum=2.0, step=0.05, value=1.0, scale=3)
                        components[K.LORA_TARGETS] = gr.CheckboxGroup(label="Target Models", choices=["transformer", "text_encoder", "text_encoder_2"], value=["text_encoder"], scale=3)

                with gr.Accordion("Advanced Settings", open=False):
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
                    components[K.LATENT_WINDOW_SIZE_SLIDER] = gr.Slider(label="Latent Window Size", minimum=1, maximum=33, value=9, step=1, visible=False, interactive=False) # Never change - FramePack Magic Number
                    components[K.OUTPUT_FOLDER_TEXTBOX] = gr.Textbox(
                        label="Output Folder",
                        value=settings_manager_instance.get_initial_output_folder()
                    )
                    components[K.SAVE_AS_DEFAULT_WORKSPACE_BUTTON] = gr.Button("Save as Default Workspace", variant="secondary")
                    components[K.RELAUNCH_NOTIFICATION_MD] = gr.Markdown("ℹ️ **Restart required** for new output path to take effect.", visible=False)
            with gr.Column(scale=2):
                with gr.Row():
                    with gr.Column(scale=2):
                        components[K.TOTAL_SEGMENTS_DISPLAY] = gr.Markdown("Calculated Total Segments: N/A", elem_id="total_segments_display")
                    with gr.Column(scale=1):
                        components[K.QUEUE_ETA_DISPLAY] = gr.Markdown("", elem_id="queue_eta_display")
                with gr.Row(equal_height=True):
                    components[K.PREVIEW_FREQUENCY_SLIDER] = gr.Slider(label="Interval of periodic automatic previews", minimum=0, maximum=100, value=5, step=1)
                    components[K.PREVIEW_SPECIFIED_SEGMENTS_TEXTBOX] = gr.Textbox(label="Comma-separated specific segments to preview", value="")
                components[K.PROCESS_QUEUE_BUTTON] = gr.Button("▶️ Process Queue", variant="primary", interactive=False)
                components[K.CREATE_PREVIEW_BUTTON] = gr.Button("📸 Generate a preview for the currently processing segment", variant="secondary", interactive=False, elem_id="create_preview_button")
                components[K.LAST_FINISHED_VIDEO] = gr.Video(interactive=True, autoplay=False, height=540)

    return components
