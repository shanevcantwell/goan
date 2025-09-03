# core/model_loader.py
import torch
import gc
import logging
from ui.shared_state import shared_state_instance
from diffusers import AutoencoderKLHunyuanVideo
from transformers import (
    LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer,
    SiglipImageProcessor, SiglipVisionModel
)
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked # type: ignore
from diffusers_helper.memory import cpu, gpu, get_cuda_free_memory_gb, DynamicSwapInstaller

logger = logging.getLogger(__name__)

# --- Model Repository Constants ---
HUNYUAN_VIDEO_REPO = "hunyuanvideo-community/HunyuanVideo"
FRAME_PACK_REPO = "lllyasviel/FramePackI2V_HY"
FLUX_REDUX_REPO = "lllyasviel/flux_redux_bfl"

def _load_transformer_model():
    """Helper to load and configure the transformer model."""
    logger.info("Loading transformer ...")

    is_legacy = shared_state_instance.system_info.get('is_legacy_gpu', False)
    # Legacy GPUs (< SM8.0) do not support bfloat16. We must use float32 for compatibility.
    # This will use more VRAM but is necessary to prevent crashes.
    transformer_dtype = torch.float32 if is_legacy else torch.bfloat16

    if is_legacy:
        logger.info(f"Legacy GPU: Loading transformer with dtype torch.float32 for compatibility.")
    else:
        logger.info(f"Modern GPU: Loading transformer with dtype torch.bfloat16")

    transformer = HunyuanVideoTransformer3DModelPacked.from_pretrained(
        FRAME_PACK_REPO, torch_dtype=transformer_dtype,
    ).cpu()
    transformer.eval()
    # Set a default value for the FP32 output flag. The worker in generation_core.py
    # will override this based on the user's UI selection and hardware for each task.
    transformer.high_quality_fp32_output_for_inference = False
    transformer = transformer.to(dtype=transformer_dtype)
    transformer.requires_grad_(False)
    logger.info("Transformer loaded successfully.")
    return transformer

def load_and_configure_models():
    """
    Detects GPU capability, loads the appropriate models, configures them for the
    detected hardware (VRAM, dtype), and populates the shared_state.
    """
    logger.info("Initializing and configuring all models...")
    try:
        # The implementation of the HunyuanVideoTransformer3DModelPacked model class
        # contains fallback logic to ensure compatibility with older GPUs.
        try:
            major_capability, _ = torch.cuda.get_device_capability()
            if major_capability < 8:
                logger.warning(f"Legacy GPU detected (Compute Capability {major_capability}.x). Activating compatibility mode.")
                shared_state_instance.system_info['is_legacy_gpu'] = True
        except Exception as e:
            logger.error(f"Could not determine GPU capability. Assuming modern GPU. Error: {e}", exc_info=True)

        free_mem_gb = get_cuda_free_memory_gb(gpu)
        high_vram = free_mem_gb > 60
        logger.info(f'Free VRAM: {free_mem_gb:.2f} GB. High-VRAM Mode: {high_vram}')

        # --- Model Loading ---
        # The following models form a tightly coupled system. The main transformer was trained
        # specifically with the outputs of these text and image encoders. Swapping them with
        # other models (e.g., a different CLIP variant) without retraining the transformer
        # is not feasible and would result in poor or nonsensical output.
        shared_state_instance.models.update({
            'text_encoder': LlamaModel.from_pretrained(HUNYUAN_VIDEO_REPO, subfolder='text_encoder', torch_dtype=torch.float16).cpu(),
            'text_encoder_2': CLIPTextModel.from_pretrained(HUNYUAN_VIDEO_REPO, subfolder='text_encoder_2', torch_dtype=torch.float16).cpu(),
            'tokenizer': LlamaTokenizerFast.from_pretrained(HUNYUAN_VIDEO_REPO, subfolder='tokenizer', legacy=False),
            'tokenizer_2': CLIPTokenizer.from_pretrained(HUNYUAN_VIDEO_REPO, subfolder='tokenizer_2', legacy=False),
            # VAE is loaded as fp16 but will be manually cast to fp32 in the worker for low-vram mode.
            'vae': AutoencoderKLHunyuanVideo.from_pretrained(HUNYUAN_VIDEO_REPO, subfolder='vae', torch_dtype=torch.float16).cpu(),
            'feature_extractor': SiglipImageProcessor.from_pretrained(FLUX_REDUX_REPO, subfolder='feature_extractor'),
            'image_encoder': SiglipVisionModel.from_pretrained(FLUX_REDUX_REPO, subfolder='image_encoder', torch_dtype=torch.float16).cpu(),
            'high_vram': high_vram,
        })
        # Initialize transformer as None and load it lazily
        shared_state_instance.models['transformer'] = None
        logger.info("All auxiliary models loaded to CPU. Configuring...")

        # Configure models based on environment
        for model_name in ['vae', 'text_encoder', 'text_encoder_2', 'image_encoder']:
            shared_state_instance.models[model_name].eval()

        if not high_vram:
            shared_state_instance.models['vae'].enable_slicing()
            shared_state_instance.models['vae'].enable_tiling()

        # Set the data types for the auxiliary models.
        for model_name, dtype in [('vae', torch.float16), ('image_encoder', torch.float16), ('text_encoder', torch.float16), ('text_encoder_2', torch.float16)]:
            shared_state_instance.models[model_name].to(dtype=dtype)

        for model_obj in shared_state_instance.models.values():
            if isinstance(model_obj, torch.nn.Module): 
                model_obj.requires_grad_(False)

        # Move initial models to GPU or install DynamicSwap
        if not high_vram:
            logger.info("Low VRAM mode: Installing DynamicSwap for auxiliary models.")
            swapper_compatible_models = ['text_encoder', 'text_encoder_2', 'image_encoder']
            for model_name in swapper_compatible_models:
                if model_name in shared_state_instance.models:
                    logger.info(f"  - Installing DynamicSwap for: {model_name}")
                    DynamicSwapInstaller.install_model(shared_state_instance.models[model_name], device=gpu)
        else:
            logger.info("High VRAM mode: Moving all auxiliary models to GPU.")
            for model_name in ['text_encoder', 'text_encoder_2', 'image_encoder', 'vae']:
                shared_state_instance.models[model_name].to(gpu)

        logger.info("Initial model configuration and placement complete.")
    except Exception as e:
        logger.critical(f"A critical error occurred during model loading: {e}", exc_info=True)
        raise

def get_transformer_model(force_reload=False):
    """Ensures the transformer model is loaded and returns it."""
    if shared_state_instance.models.get('transformer') is None or force_reload:
        if shared_state_instance.models.get('transformer') is not None: # If forcing reload, clear old model
            del shared_state_instance.models['transformer']
            gc.collect()
            torch.cuda.empty_cache()
        shared_state_instance.models['transformer'] = _load_transformer_model()
        if not shared_state_instance.models['high_vram']:
            # The transformer is also compatible with the swapper and is installed here
            # after being lazy-loaded.
            logger.info(f"  - Installing DynamicSwap for: transformer")
            DynamicSwapInstaller.install_model(shared_state_instance.models['transformer'], device=gpu)
        else:
            shared_state_instance.models['transformer'].to(gpu)
    return shared_state_instance.models['transformer']
