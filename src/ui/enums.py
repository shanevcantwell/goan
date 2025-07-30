# ui/enums.py
from enum import StrEnum, auto

class ComponentKey(StrEnum):
    """
    Enumeration of all Gradio component keys.
    Using StrEnum means the value of each member is its own name,
    making it easy to debug and use while providing type-safety.
    """
    # High-level Components
    BLOCK = auto()
    APP_STATE = auto()

    # --- State Components ---
    LORA_NAME_STATE = auto()
    EXTRACTED_METADATA_STATE = auto()
    HANDLER_OUTPUT_STATE = auto() # A generic state to hold the output dict from a handler
    METADATA_MODAL_TRIGGER_STATE = auto()

    # --- Main UI Columns & Controls ---
    IMAGE_FILE_INPUT = auto()
    INPUT_IMAGE_DISPLAY = auto()
    ADD_TASK_BUTTON = auto()
    CLEAR_IMAGE_BUTTON = auto()
    DOWNLOAD_IMAGE_BUTTON = auto()
    PROCESS_QUEUE_BUTTON = auto()
    PROGRESS_ROW = auto()
    CREATE_PREVIEW_BUTTON = auto()
    # CANCEL_EDIT_TASK_BUTTON = auto()
    POSITIVE_PROMPT = auto()
    NEGATIVE_PROMPT = auto()
    VIDEO_LENGTH_SLIDER = auto()
    SEED = auto()
    IMAGE_DOWNLOADER = auto()
    QUEUE_DOWNLOADER = auto()

    # --- Metadata Modal ---
    METADATA_MODAL = auto()
    METADATA_PROMPT_PREVIEW = auto()
    # METADATA_OVERWRITE_SEED_CHECKBOX = auto()
    CANCEL_METADATA_BUTTON = auto()
    CONFIRM_METADATA_BUTTON = auto()

    # --- Task Queue ---
    QUEUE_DF = auto()
    SAVE_QUEUE_BUTTON = auto()
    LOAD_QUEUE_BUTTON = auto()
    CLEAR_QUEUE_BUTTON = auto()
    
    # --- Live Progress Feedback ---
    SEGMENT_PROGRESS_BAR = auto()
    SEGMENT_ETA_DISPLAY = auto()
    QUEUE_PROGRESS_BAR = auto()
    QUEUE_ETA_DISPLAY = auto()

    # --- Live Preview & Output ---
    CURRENT_TASK_PREVIEW_IMAGE = auto()
    CURRENT_TASK_PROGRESS_DESCRIPTION = auto()
    CURRENT_TASK_PROGRESS_BAR = auto()
    LAST_FINISHED_VIDEO = auto()
    FULL_WIDTH_LAYOUT_ROW = auto()
    LAST_FINISHED_VIDEO_FULL_WIDTH = auto()

    # --- Accordions & Advanced Settings ---
    PREVIEW_FREQUENCY_SLIDER = auto()
    PREVIEW_SPECIFIED_SEGMENTS_TEXTBOX = auto()
    FPS_SLIDER = auto()

    # --- Settings Panels ---
    SETTINGS_MENU_CHECKBOX_GROUP = auto()
    POWER_USER_GROUP = auto()
    LORA_GROUP = auto()
    ADVANCED_SETTINGS_GROUP = auto()

    # --- Power User Settings ---
    DISTILLED_CFG_START_SLIDER = auto()
    VARIABLE_CFG_SHAPE_RADIO = auto()
    DISTILLED_CFG_END_SLIDER = auto()
    REAL_CFG_SLIDER = auto()
    GUIDANCE_RESCALE_SLIDER = auto()
    ROLL_OFF_START_SLIDER = auto()
    ROLL_OFF_FACTOR_SLIDER = auto()
    STEPS_SLIDER = auto()

    # --- LoRA Settings ---
    LORA_UPLOAD_BUTTON = auto()
    LORA_REFRESH_BUTTON = auto()
    LORA_NAMES = auto()
    LORA_WEIGHT = auto()
    LORA_TARGETS = auto()
    LORA_ROW = auto()
    LORA_NAME = auto()

    # --- Advanced Settings Group ---
    USE_TEACACHE_CHECKBOX = auto()
    USE_FP32_TRANSFORMER_OUTPUT_CHECKBOX = auto()
    FORCE_STANDARD_FPS_CHECKBOX = auto()
    GPU_MEMORY_PRESERVATION_SLIDER = auto()
    SHOW_HIDDEN_ELEMENTS_CHECKBOX = auto()
    MP4_CRF_SLIDER = auto()
    LATENT_WINDOW_SIZE_SLIDER = auto()  # FramePack configuration setting to set to 9 and leave alone
    OUTPUT_FOLDER_TEXTBOX = auto()
    
    # --- Workspace ---
    SAVE_AS_DEFAULT_WORKSPACE_BUTTON = auto()
    RELAUNCH_NOTIFICATION_MD = auto()
