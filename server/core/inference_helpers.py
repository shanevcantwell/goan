# src/core/inference_helpers.py
# Contains helper functions for the core inference logic, refactored from generation_utils.py
import logging
import torch
import einops
import numpy as np
from typing import Optional, Dict

from diffusers_helper.memory import load_model_as_complete, unload_complete_models, gpu, fake_diffusers_current_device
from diffusers_helper.hunyuan import encode_prompt_conds, vae_encode, vae_decode_fake, vae_decode
from diffusers_helper.utils import crop_or_pad_yield_mask, soft_append_bcthw
from diffusers_helper.gradio.progress_bar import make_progress_bar_html
from diffusers_helper.clip_vision import hf_clip_vision_encode

logger = logging.getLogger(__name__)

def generate_roll_off_schedule(
    total_steps: int,
    peak_cfg: float,
    final_cfg: float,
    roll_off_start_percent: float,
    roll_off_factor: float
) -> list[float]:
    """
    Generates a CFG schedule that holds a peak value and then rolls off.
    """
    ramp_down_start_step = int(round(total_steps * roll_off_start_percent))
    sustain_steps = ramp_down_start_step
    ramp_steps = total_steps - sustain_steps
    
    if ramp_steps <= 0:
        return np.full(total_steps, peak_cfg).tolist()

    sustain_phase = np.full(sustain_steps, peak_cfg)
    t = np.linspace(0, 1, ramp_steps)
    t_curved = t ** roll_off_factor
    roll_off_phase = peak_cfg + (final_cfg - peak_cfg) * t_curved
    full_schedule = np.concatenate([sustain_phase, roll_off_phase])
    
    return full_schedule.tolist()

def calculate_current_segment_cfg(
    variable_cfg_shape: str,
    total_latent_sections: int,
    latent_padding_iteration: int,
    initial_gs_from_ui: float,
    distilled_cfg_end_value_for_schedule: float,
    roll_off_start: float,
    roll_off_factor: float
) -> float:
    """
    Calculates the guidance scale for the current segment based on the selected schedule.
    """
    current_segment_gs_to_use = initial_gs_from_ui
    if variable_cfg_shape != 'Off' and total_latent_sections > 1:
        progress = latent_padding_iteration / (total_latent_sections - 1) if total_latent_sections > 1 else 0
        if variable_cfg_shape == 'Linear':
            current_segment_gs_to_use = initial_gs_from_ui + (distilled_cfg_end_value_for_schedule - initial_gs_from_ui) * progress
        elif variable_cfg_shape == 'Roll-off':
            roll_off_start_point = roll_off_start / 100.0
            if progress < roll_off_start_point:
                current_segment_gs_to_use = initial_gs_from_ui
            else:
                denominator = (1.0 - roll_off_start_point)
                if denominator > 0:
                    roll_off_progress = (progress - roll_off_start_point) / denominator
                    curved_progress = roll_off_progress ** roll_off_factor
                    current_segment_gs_to_use = initial_gs_from_ui + (distilled_cfg_end_value_for_schedule - initial_gs_from_ui) * curved_progress
                else:
                    current_segment_gs_to_use = distilled_cfg_end_value_for_schedule
    return current_segment_gs_to_use

def diffusion_step_callback(
    d: dict,
    task_id: str,
    output_queue_ref,
    current_loop_segment_number: int,
    total_latent_sections: int,
    steps: int,
    history_pixels: Optional[torch.Tensor],
    fps: int,
):
    """
    Handles progress updates during the diffusion sampling loop for a single step.
    """
    current_diffusion_step = d["i"] + 1
    preview_latent = d["denoised"]
    preview_img_np = vae_decode_fake(preview_latent)
    preview_img_np = ((preview_img_np * 255.0).detach().cpu().numpy().clip(0, 255).astype(np.uint8))
    preview_img_np = einops.rearrange(preview_img_np, "b c t h w -> (b h) (t w) c")

    percentage = int(100.0 * current_diffusion_step / steps)
    hint = f"Segment {current_loop_segment_number}, Sampling {current_diffusion_step}/{steps}"
    current_video_frames_count = (history_pixels.shape[2] if history_pixels is not None else 0)
    desc = f"Task {task_id}: Vid Frames: {current_video_frames_count}, Len: {current_video_frames_count / fps :.2f}s. Seg {current_loop_segment_number}/{total_latent_sections}. Extending..."
    output_queue_ref.push(('progress', (task_id, preview_img_np, desc, make_progress_bar_html(percentage, hint))))

def prepare_segment_latents(
    latent_padding_size: int,
    latent_window_size: int,
    start_latent: torch.Tensor,
    history_latents: torch.Tensor,
) -> Dict[str, torch.Tensor]:
    """
    Prepares the various latent tensors and indices required for a single generation segment.
    """
    indices = torch.arange(
        0,
        sum([1, latent_padding_size, latent_window_size, 1, 2, 16]),
        device="cpu",
    ).unsqueeze(0)
    (
        clean_latent_indices_pre,
        _,
        latent_indices,
        clean_latent_indices_post,
        clean_latent_2x_indices,
        clean_latent_4x_indices,
    ) = indices.split(
        [1, latent_padding_size, latent_window_size, 1, 2, 16], dim=1
    )
    clean_latents_pre = start_latent.to(
        history_latents.device, dtype=history_latents.dtype
    )
    clean_latent_indices = torch.cat(
        [clean_latent_indices_pre, clean_latent_indices_post], dim=1
    )

    clean_latents_post, clean_latents_2x, clean_latents_4x = history_latents[
        :, :, : 1 + 2 + 16, :, :
    ].split([1, 2, 16], dim=2)
    clean_latents = torch.cat([clean_latents_pre, clean_latents_post], dim=2)

    return {
        'latent_indices': latent_indices,
        'clean_latents': clean_latents,
        'clean_latent_indices': clean_latent_indices,
        'clean_latents_2x': clean_latents_2x,
        'clean_latent_2x_indices': clean_latent_2x_indices,
        'clean_latents_4x': clean_latents_4x,
        'clean_latent_4x_indices': clean_latent_4x_indices,
    }

def update_pixel_history(
    history_pixels: Optional[torch.Tensor],
    real_history_latents: torch.Tensor,
    vae,
    latent_window_size: int,
    is_last_section: bool,
    high_vram: bool,
) -> torch.Tensor:
    """
    Decodes the latest generated latents and appends them to the pixel history,
    handling the initial case and subsequent soft-appending.
    Manages VAE model loading for low-VRAM mode.
    """
    if not high_vram:
        load_model_as_complete(vae, target_device=gpu)

    new_history_pixels = vae_decode(real_history_latents, vae).cpu() if history_pixels is None else soft_append_bcthw(vae_decode(real_history_latents[:, :, :((latent_window_size * 2 + 1) if is_last_section else (latent_window_size * 2))], vae).cpu(), history_pixels, latent_window_size * 4 - 3)

    if not high_vram: unload_complete_models(vae)
    return new_history_pixels

def prepare_conditioning_tensors(
    prompt: str,
    negative_prompt: str,
    text_encoder,
    text_encoder_2,
    tokenizer,
    tokenizer_2,
    input_image_np: np.ndarray,
    feature_extractor,
    image_encoder,
    vae,
    transformer,
    real_cfg: float,
    high_vram: bool,
    output_queue_ref,
    task_id: str,
    total_latent_sections: int,
) -> Dict[str, torch.Tensor]:
    """
    Encapsulates the logic for preparing all conditioning tensors required by the diffusion model.
    """
    if not high_vram:
        unload_complete_models()

    output_queue_ref.push(('progress', (task_id, None, f'Total Segments: {total_latent_sections}', make_progress_bar_html(0, "Text encoding ..."))))
    if not high_vram:
        fake_diffusers_current_device(text_encoder, gpu)
        load_model_as_complete(text_encoder_2, target_device=gpu)
    
    llama_vec, clip_l_pooler = encode_prompt_conds(prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)
    llama_vec_n, clip_l_pooler_n = (torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)) if real_cfg == 1 else encode_prompt_conds(negative_prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)
    
    llama_vec, llama_attention_mask = crop_or_pad_yield_mask(llama_vec, length=512)
    llama_vec_n, llama_attention_mask_n = crop_or_pad_yield_mask(llama_vec_n, length=512)
    
    input_image_pt = (torch.from_numpy(input_image_np).float().permute(2, 0, 1).unsqueeze(0) / 127.5 - 1.0)[:, :, None, :, :]
    
    output_queue_ref.push(('progress', (task_id, None, f'Total Segments: {total_latent_sections}', make_progress_bar_html(0, "VAE encoding ..."))))
    if not high_vram:
        load_model_as_complete(vae, target_device=gpu)
    start_latent = vae_encode(input_image_pt, vae)
    
    output_queue_ref.push(('progress', (task_id, None, f'Total Segments: {total_latent_sections}', make_progress_bar_html(0, "CLIP Vision encoding ..."))))
    if not high_vram:
        load_model_as_complete(image_encoder, target_device=gpu)
    
    image_encoder_output = hf_clip_vision_encode(input_image_np, feature_extractor, image_encoder)
    image_encoder_last_hidden_state = image_encoder_output.last_hidden_state
    
    conditioning_tensors = {
        'llama_vec': llama_vec,
        'llama_attention_mask': llama_attention_mask,
        'clip_l_pooler': clip_l_pooler,
        'llama_vec_n': llama_vec_n,
        'llama_attention_mask_n': llama_attention_mask_n,
        'clip_l_pooler_n': clip_l_pooler_n,
        'start_latent': start_latent,
        'image_encoder_last_hidden_state': image_encoder_last_hidden_state,
    }

    # Selectively convert only the tensors that need to match the transformer's dtype.
    # CRITICAL: The attention masks must remain as integer-like tensors for slicing,
    # and start_latent should remain float32 for the history buffer. This mirrors
    # the logic from the original, working implementation.
    keys_to_convert = [
        'llama_vec',
        'llama_vec_n',
        'clip_l_pooler',
        'clip_l_pooler_n',
        'image_encoder_last_hidden_state',
    ]
    for key in keys_to_convert:
        conditioning_tensors[key] = conditioning_tensors[key].to(transformer.dtype)
        
    return conditioning_tensors