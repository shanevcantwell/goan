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
    components[K.BLOCK] = gr.Blocks(css=APP_CSS, title="goan alpha 0.2").queue()

    with components[K.BLOCK]:
        # State components
        components[K.APP_STATE] = gr.State({
            "queue_state": {"queue": [], "next_id": 1, "processing": False, "editing_task_id": None},
            "last_completed_video_path": None,
            "lora_state": {"loaded_loras": {}}
        })
        components[K.LORA_NAME_STATE] = gr.Textbox(visible=False, label="LoRA Names State")
        components[K.EXTRACTED_METADATA_STATE] = gr.State({})
        components[K.HANDLER_OUTPUT_STATE] = gr.State({})
        components[K.METADATA_MODAL_TRIGGER_STATE] = gr.Textbox(visible=False)

        gr.Markdown('# goan (Powered by FramePack) a0.2')

        # Metadata Modal
        with Modal(visible=False) as metadata_modal:
            components[K.METADATA_MODAL] = metadata_modal
            gr.Markdown("Image has saved parameters. Overwrite current creative settings?")
            components[K.METADATA_PROMPT_PREVIEW] = gr.Textbox(label="Detected Prompt", interactive=False, lines=5, max_lines=10)
            with gr.Row():
                components[K.CANCEL_METADATA_BUTTON] = gr.Button("No", variant="secondary")
                components[K.CONFIRM_METADATA_BUTTON] = gr.Button("Yes, Apply", variant="primary")

        # --- Top Section ---
        with gr.Group(elem_classes="top-section-container"):
            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    components[K.IMAGE_FILE_INPUT] = gr.File(label="Drop Final Image for I2V", file_types=["image"], elem_id="image_file_input_ui")
                    components[K.INPUT_IMAGE_DISPLAY] = gr.Image(type="pil", label="Current Input Image", interactive=False, visible=False, height=220, show_download_button=False, elem_id="input_image_display_ui", elem_classes="flat-input")
                    components[K.CLEAR_IMAGE_BUTTON] = gr.Button("Replace Image", interactive=False, elem_id="clear_image_button", scale=1, variant="secondary")
                    components[K.DOWNLOAD_IMAGE_BUTTON] = gr.Button("Download Image with Metadata", interactive=False, elem_id="download_image_button", scale=1, variant="secondary")
                    components[K.SEED] = gr.Number(label="Seed", value=-1, precision=0, minimum=-1, maximum=2**32 - 1)
                with gr.Column(scale=2, min_width=600):
                    components[K.POSITIVE_PROMPT] = gr.Textbox(label="Prompt", lines=7, max_lines=7, elem_id="positive_prompt", elem_classes="flat-input")
                    components[K.NEGATIVE_PROMPT] = gr.Textbox(label="Negative Prompt", lines=2, elem_id="negative_prompt", elem_classes="flat-input")

        # --- Bottom Section ---
        with gr.Group(elem_classes="bottom-section-container"):
            # Hidden file components for one-click downloads
            with gr.Group(visible=False):
                components[K.IMAGE_DOWNLOADER] = gr.File(elem_id="image_downloader_hidden_file")
                components[K.QUEUE_DOWNLOADER] = gr.File(elem_id="queue_downloader_hidden_file")

            with gr.Row(equal_height=True):
                with gr.Column(scale=1):
                    components[K.VIDEO_LENGTH_SLIDER] = gr.Slider(
                        label="Video Length (s)",
                        show_label=True,
                        minimum=0.1, maximum=120, value=5.0, step=0.1
                    )
                with gr.Column(scale=2):
                    with gr.Row(equal_height=True, elem_classes="compact-row"):
                        components[K.PREVIEW_FREQUENCY_SLIDER] = gr.Slider(label="Preview Interval", minimum=0, maximum=100, value=5, step=1, container=False)
                        components[K.PREVIEW_SPECIFIED_SEGMENTS_TEXTBOX] = gr.Textbox(label="Preview Segments (eg: 3,5,10)", value="", scale=1, elem_classes="flat-input")
            with gr.Row(equal_height=True):
                with gr.Column(scale=1):
                    components[K.ADD_TASK_BUTTON] = gr.Button("Add to Queue", interactive=False, variant="primary")
                with gr.Column(scale=2):
                    components[K.PROCESS_QUEUE_BUTTON] = gr.Button("▶️ Process Queue", variant="primary", interactive=False)
            with gr.Row(equal_height=True):
                components[K.SEGMENT_PROGRESS_BAR] = gr.HTML('', elem_id="segment_progress_bar_ui", visible=True)
                components[K.SEGMENT_ETA_DISPLAY] = gr.Markdown('', elem_id="segment_eta_display_ui", visible=True)
            with gr.Row(equal_height=True):
                components[K.CURRENT_TASK_PROGRESS_BAR] = gr.HTML('', elem_id="current_task_progress_bar_ui", visible=False)
                components[K.CURRENT_TASK_PROGRESS_DESCRIPTION] = gr.Markdown('', elem_id="current_task_progress_description_ui", visible=False)

            components[K.QUEUE_DF] = gr.DataFrame(
                headers=["Status", "Prompt", "Image", "Length (s)", "ID"],
                datatype=["markdown", "html", "markdown", "number", "number"],
                elem_id="queue_df",
                max_height=350,
                interactive=False
            )
            with gr.Row(elem_classes="button-group"):
                components[K.SAVE_QUEUE_BUTTON] = gr.Button("Save Queue", interactive=False, variant="secondary")
                components[K.LOAD_QUEUE_BUTTON] = gr.UploadButton("Load Queue", file_types=[".zip"], variant="primary")
                components[K.CLEAR_QUEUE_BUTTON] = gr.Button("Clear Pending", variant="stop", interactive=False)

            # Settings menus
            with gr.Row(equal_height=True):
                with gr.Column(scale=1):
                    components[K.SETTINGS_MENU_CHECKBOX_GROUP] = gr.CheckboxGroup(
                        ["Power User", "LoRA", "Advanced"],
                        value=None,
                        elem_id="settings_menu_checkbox_group",
                        elem_classes=["button-group", "borderless-container"],
                        type="value",
                        interactive=True,
                    )
                with gr.Column(scale=2):
                    components[K.CREATE_PREVIEW_BUTTON] = gr.Button("📸 Generate a preview for the currently processing segment", variant="secondary", interactive=False, elem_id="create_preview_button")

            with gr.Row(equal_height=True):
                with gr.Column(scale=1):
                    with gr.Group(visible=False, elem_classes="compact-group") as power_user_group:
                        components[K.POWER_USER_GROUP] = power_user_group
                        components[K.VARIABLE_CFG_SHAPE_RADIO] = gr.Radio(["Off", "Linear", "Roll-off"], label="Variable CFG", value="Off")
                        with gr.Row(elem_classes="compact-row"):
                            components[K.DISTILLED_CFG_START_SLIDER] = gr.Slider(label="Distilled CFG Start", minimum=1.0, maximum=32.0, value=10.0, step=0.01, container=False)
                            components[K.DISTILLED_CFG_END_SLIDER] = gr.Slider(label="Distilled CFG End", minimum=1.0, maximum=32.0, value=10.0, step=0.01, interactive=False, visible=False, container=False)
                        with gr.Row(elem_classes="compact-row"):
                            components[K.ROLL_OFF_START_SLIDER] = gr.Slider(label="Roll-off Start %", minimum=0, maximum=100, value=75, step=1, visible=False, container=False)
                            components[K.ROLL_OFF_FACTOR_SLIDER] = gr.Slider(label="Roll-off Curve Factor", minimum=0.25, maximum=4.0, value=1.0, step=0.05, visible=False, container=False)
                        with gr.Row(elem_classes="compact-row"):
                            components[K.REAL_CFG_SLIDER] = gr.Slider(label="CFG (Real)", minimum=1.0, maximum=8.0, value=1.5, step=0.01, container=False)
                            components[K.STEPS_SLIDER] = gr.Slider(label="Steps", minimum=1, maximum=100, value=25, step=1, container=False)
                        with gr.Row(elem_classes="compact-row"):
                            components[K.GUIDANCE_RESCALE_SLIDER] = gr.Slider(label="RS", minimum=0.0, maximum=32.0, value=0.0, step=0.01, visible=False, container=False)

                    with gr.Group(visible=False) as lora_group:
                        components[K.LORA_GROUP] = lora_group
                        gr.Markdown("🧪 **Experimental LoRA Support**...")
                        components[K.LORA_UPLOAD_BUTTON] = gr.UploadButton("Upload LoRA", file_types=[".safetensors"], file_count="single", size="sm", variant="secondary")
                        with gr.Row(visible=False, variant="panel") as lora_row_0_ctx:
                            components[K.LORA_ROW] = lora_row_0_ctx
                            components[K.LORA_NAME] = gr.Textbox(label="LoRA Name", interactive=False, scale=2)
                            components[K.LORA_WEIGHT] = gr.Slider(label="Weight", minimum=-2.0, maximum=2.0, step=0.05, value=1.0, scale=3, container=False)
                            components[K.LORA_TARGETS] = gr.CheckboxGroup(label="Target Models", choices=["transformer", "text_encoder", "text_encoder_2"], value=["text_encoder"], scale=3)

                    with gr.Group(visible=False) as advanced_settings_group:
                        components[K.ADVANCED_SETTINGS_GROUP] = advanced_settings_group
                        components[K.USE_TEACACHE_CHECKBOX] = gr.Checkbox(label='Use TeaCache', value=True)
                        is_legacy_gpu = shared_state_module.shared_state_instance.system_info.get('is_legacy_gpu', False)
                        components[K.USE_FP32_TRANSFORMER_OUTPUT_CHECKBOX] = gr.Checkbox(label="Use FP32 Transformer Output", value=False, visible=not is_legacy_gpu, info="...")
                        with gr.Row(elem_classes="compact-row"):
                            components[K.GPU_MEMORY_PRESERVATION_SLIDER] = gr.Slider(label="GPU Preserve (GB)", minimum=4, maximum=128, value=6.0, step=0.1, container=False)
                            components[K.FPS_SLIDER] = gr.Slider(label="MP4 Framerate (FPS)", minimum=1, maximum=60, value=30, step=1, container=False)
                        with gr.Row(elem_classes="compact-row"):
                            components[K.MP4_CRF_SLIDER] = gr.Slider(label="MP4 CRF", minimum=0, maximum=51, value=18, step=1, container=False)
                        components[K.LATENT_WINDOW_SIZE_SLIDER] = gr.Slider(label="Latent Window", minimum=1, maximum=33, value=9, step=1, visible=True, interactive=True, container=False)
                        components[K.OUTPUT_FOLDER_TEXTBOX] = gr.Textbox(label="Output Folder", value=settings_manager_instance.get_initial_output_folder())
                        components[K.SAVE_AS_DEFAULT_WORKSPACE_BUTTON] = gr.Button("Save as Default Workspace", variant="secondary")
                        components[K.RELAUNCH_NOTIFICATION_MD] = gr.Markdown("ℹ️ **Restart required**...", visible=False)

                with gr.Column(scale=2):
                    components[K.LAST_FINISHED_VIDEO] = gr.Video(visible=False, autoplay=False, height=540)
                    components[K.MANUAL_PREVIEW_IMAGE] = gr.Image(label="Manual Preview", interactive=False, visible=False, height=220, show_download_button=False, elem_id="manual_preview_image_ui", elem_classes="flat-input")

            # Full width video
            with gr.Row() as full_width_layout_row:
                components[K.FULL_WIDTH_LAYOUT_ROW] = full_width_layout_row
                components[K.LAST_FINISHED_VIDEO_FULL_WIDTH] = gr.Video(interactive=True, autoplay=False, label="Video Preview")

            with gr.Row(visible=False):
                components[K.CURRENT_TASK_PREVIEW_IMAGE] = gr.Image(
                    label=None, interactive=False, visible=False, show_download_button=False,
                    elem_id="current_task_preview_image_ui", elem_classes="flat-input"
                )

    return components
