# core/generation_utils.py
# Contains helper functions refactored from generation_core.py
import logging
import os
import json
import io
import zipfile
import torch
import einops
from PIL import Image
from collections import deque
import numpy as np
from typing import Optional, Tuple, Set, Dict

from ui.shared_state import shared_state_instance
from diffusers_helper.memory import load_model_as_complete, unload_complete_models, gpu, fake_diffusers_current_device
from diffusers_helper.hunyuan import vae_decode, encode_prompt_conds, vae_encode
from diffusers_helper.utils import save_bcthw_as_mp4, generate_timestamp, crop_or_pad_yield_mask
from diffusers_helper.gradio.progress_bar import make_progress_bar_html

from . import generation_utils
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

    Args:
        total_steps (int): The total number of inference steps.
        peak_cfg (float): The CFG value to hold before the roll-off.
        final_cfg (float): The CFG value to ramp down to at the final step.
        roll_off_start_percent (float): The point (0.0 to 1.0) to start the roll-off.
        roll_off_factor (float): The exponential factor for the curve (1.0 is linear).

    Returns:
        list[float]: A list of CFG values, one for each step.
    """
    # Calculate the step at which the ramp-down begins
    ramp_down_start_step = int(round(total_steps * roll_off_start_percent))
    
    # The number of steps to hold the peak CFG
    sustain_steps = ramp_down_start_step
    
    # The number of steps for the ramp-down phase
    ramp_steps = total_steps - sustain_steps
    
    if ramp_steps <= 0:
        # If the start point is at or after 100%, just hold the peak CFG
        return np.full(total_steps, peak_cfg).tolist()

    # Phase 1: Hold the peak CFG
    sustain_phase = np.full(sustain_steps, peak_cfg)

    # Phase 2: Generate the roll-off curve
    # Create a normalized time vector from 0 to 1 for the ramp
    t = np.linspace(0, 1, ramp_steps)
    # Apply the roll-off factor to shape the curve
    t_curved = t ** roll_off_factor
    
    # Interpolate from peak to final CFG along the curved timeline
    roll_off_phase = peak_cfg + (final_cfg - peak_cfg) * t_curved

    # Combine the phases and return
    full_schedule = np.concatenate([sustain_phase, roll_off_phase])
    
    return full_schedule.tolist()


def initialize_job(
    total_second_length: float,
    fps: int,
    latent_window_size: int,
    task_id: str,
    output_queue_ref,
) -> Tuple[int, str]:
    """
    Calculates job parameters, creates a job ID, and sends an initial progress update.
    This is the first "secret sauce" block.
    """
    # A "segment" or "section" is one generation loop, which produces (LWS * 4 - 3) frames.
    total_frames = int(total_second_length * fps)
    frames_per_segment = latent_window_size * 4 - 3
    total_latent_sections = (
        int(max(round(total_frames / frames_per_segment), 1))
        if frames_per_segment > 0
        else 1
    )

    job_id = f"{generate_timestamp()}_task{task_id}"
    output_queue_ref.push(
        (
            "progress",
            (
                task_id,
                None,
                f"Total Segments: {total_latent_sections}",
                make_progress_bar_html(0, "Starting ..."),
            ),
        )
    )
    return total_latent_sections, job_id


# Replace the old handle_segment_saving function with this updated version.

def handle_segment_saving(
    # Loop state
    latent_padding_iteration: int,
    is_last_section: bool,
    current_loop_segment_number: int,
    total_latent_sections: int,
    current_video_frame_count: int,
    history_pixels,
    # Job/Task info
    task_id: str,
    job_id: str,
    output_queue_ref,
    outputs_folder: str,
    # User settings
    preview_frequency: int,
    parsed_segments_to_decode_set: Set[int],
    fps: int,
    mp4_crf: int,
    force_standard_fps: bool = False,
    # Add new argument to receive the request status from the worker.
    is_manual_request: bool = False
) -> Optional[str]:
    """
    Handles the logic for saving an MP4 for the current segment, either automatically
    or by user request. This is the second "secret sauce" block.
    Returns the path to the saved file, or None if no file was saved.
    """
    # The logic to check the global flag is removed from this function.

    # Determine if we should save based on any of the automatic criteria.
    should_save_automatically = (
        latent_padding_iteration == 0  # Always save the very first segment
        or is_last_section  # Always save the final completed video
        or (
            parsed_segments_to_decode_set
            and current_loop_segment_number in parsed_segments_to_decode_set
        )  # Save if the user specified this segment number
        or (
            preview_frequency > 0 and (current_loop_segment_number % preview_frequency == 0)
        )  # Save based on the periodic preview_frequency setting
    )

    # The main condition now uses the argument passed from the worker.
    if is_manual_request or should_save_automatically:
        # If we are saving due to a manual request, "consume" it by clearing the flag here.
        if is_manual_request:
            shared_state_instance.preview_request_flag.clear()

        save_hint = "Saving Preview..." if is_manual_request else "Saving Segment..."
        if is_last_section:
            save_hint = "Saving Final Video..."

        output_queue_ref.push(("progress", (task_id, None, f"Segment {current_loop_segment_number}/{total_latent_sections}: {save_hint}", make_progress_bar_html(100, save_hint))))

        segment_mp4_filename = os.path.join(outputs_folder, f"{job_id}_segment_{current_loop_segment_number}_frames_{current_video_frame_count}.mp4")
        save_bcthw_as_mp4(history_pixels, segment_mp4_filename, fps=fps, crf=mp4_crf)
        
        logger.info(f"Task {task_id}: SAVED MP4 for segment {current_loop_segment_number} to {segment_mp4_filename}. Total video frames: {current_video_frame_count}")
        output_queue_ref.push(("file", (task_id, segment_mp4_filename, f"Segment {current_loop_segment_number} MP4 saved ({current_video_frame_count} frames)")))
        return segment_mp4_filename
    else:
        # This part of the logic remains unchanged.
        logger.info(f"Task {task_id}: SKIPPED MP4 save for intermediate segment {current_loop_segment_number}.")
        return None

def save_resume_state(
    outputs_folder: str,
    job_id: str,
    current_loop_segment_number: int,
    history_latents: torch.Tensor,
    input_image_np: np.ndarray,
    creative_params: Dict,
    task_id: str,
    retention_count: int,
) -> Optional[str]:
    """
    Saves the current generation state to a .goan_resume zip archive.
    This is the third "secret sauce" block.
    """
    resume_dir = os.path.join(outputs_folder, "resume_states")
    os.makedirs(resume_dir, exist_ok=True)

    if retention_count == 0:
        return None # Do not save if retention is explicitly zero.

    resume_filename_base = f"{job_id}_resume_seg_{current_loop_segment_number}"
    resume_zip_path = os.path.join(resume_dir, f"{resume_filename_base}.goan_resume")

    logger.info(f"Task {task_id}: Saving resume state to {resume_zip_path}...")

    try:
        with zipfile.ZipFile(resume_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Save creative parameters to params.json
            # The passed dict contains all necessary creative & environment params.
            zf.writestr('params.json', json.dumps(creative_params, indent=4))

            # 2. Save source image to source_image.png
            img = Image.fromarray(input_image_np)
            with io.BytesIO() as buf:
                img.save(buf, format='PNG')
                zf.writestr('source_image.png', buf.getvalue())

            # 3. Save latent history to latent_history.pt
            with io.BytesIO() as buf:
                torch.save(history_latents.cpu(), buf)
                zf.writestr('latent_history.pt', buf.getvalue())

            # 4. Save job metadata to job_info.json
            job_info = {
                'job_id': job_id,
                'completed_segments': current_loop_segment_number,
            }
            zf.writestr('job_info.json', json.dumps(job_info, indent=4))

        logger.info(f"Task {task_id}: Successfully saved resume state to {resume_zip_path}")

        # --- Handle rolling file retention ---
        if retention_count > 0:
            try:
                # Find all resume files for this job_id
                all_resume_files = [f for f in os.listdir(resume_dir) if f.startswith(job_id) and f.endswith('.goan_resume')]
                if len(all_resume_files) > retention_count:
                    # Sort files to find the oldest ones. Sorting by name works due to the _seg_N suffix.
                    all_resume_files.sort(key=lambda name: int(name.split('_seg_')[1].split('.')[0]))
                    files_to_delete = all_resume_files[:-retention_count]
                    for f_del in files_to_delete:
                        os.remove(os.path.join(resume_dir, f_del))
                        logger.info(f"Task {task_id}: Deleted old resume file: {f_del}")
            except Exception as e_clean:
                logger.error(f"Task {task_id}: Error during resume file cleanup: {e_clean}", exc_info=True)
        return resume_zip_path
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to save resume state: {e}", exc_info=True)
        return None


def _save_final_preview(history_latents, vae, job_id, task_id, outputs_folder, crf, fps, output_queue_ref, high_vram):
    """
    Helper function to decode and save the final video preview during a graceful abort.
    This logic is refactored to be callable from the end of the worker.
    """
    if history_latents is None:
        logger.warning(f"Task {task_id}: No latents generated, cannot save final preview.")
        return None

    # Check for a hard abort (level 2) before starting the expensive decode.
    # This allows a double-click abort to interrupt the graceful save.
    if shared_state_instance.abort_state['level'] >= 2:
        logger.warning(f"Task {task_id}: Hard abort detected before final VAE decode.")
        raise InterruptedError("Hard abort during final save.")

    logger.info(f"Task {task_id}: Decoding final latents for graceful abort preview...")
    output_queue_ref.push(('progress', (task_id, None, "Decoding final latents for preview...", make_progress_bar_html(100, "Decoding..."))))

    if not high_vram:
        load_model_as_complete(vae, target_device=gpu)

    # This is a blocking, expensive operation, necessary only to produce mp4.
    pixels = vae_decode(history_latents, vae).cpu()

    if not high_vram:
        unload_complete_models(vae)

    # Add a second check for a hard abort after the decode, before writing the file.
    if shared_state_instance.abort_state['level'] >= 2:
        logger.warning(f"Task {task_id}: Hard abort detected before final MP4 write.")
        raise InterruptedError("Hard abort during final save.")

    logger.info(f"Task {task_id}: Writing final MP4 preview...")
    output_queue_ref.push(('progress', (task_id, None, "Writing final MP4 preview...", make_progress_bar_html(100, "Writing MP4..."))))

    final_video_path = os.path.join(outputs_folder, f'{job_id}_aborted_preview.mp4')
    save_bcthw_as_mp4(pixels, final_video_path, fps=fps, crf=crf)
    logger.info(f"Task {task_id}: Saved graceful abort preview to {final_video_path}")
    return final_video_path


def _signal_abort_to_ui(output_queue_ref, task_id, video_path):
    """Helper to send a consistently formatted abort message to the UI queue."""
    logger.info(f"Task {task_id}: Signaling abort to UI, providing video path: {video_path}")
    output_queue_ref.push(('aborted', (task_id, video_path)))
    
def _format_eta(seconds: float) -> str:
    """Formats seconds into a human-readable ETA string."""
    if seconds is None or seconds < 0:
        return "ETA: N/A"
    if seconds > 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"ETA: {hours}h {minutes}m"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"ETA: {minutes}m {secs}s"

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
    # Only apply a schedule if one is selected and there's more than one segment.
    if variable_cfg_shape != 'Off' and total_latent_sections > 1:
        # Calculate progress as a value from 0.0 to 1.0 over the segments.
        # Avoid division by zero if there's only one segment
        progress = latent_padding_iteration / (total_latent_sections - 1) if total_latent_sections > 1 else 0

        if variable_cfg_shape == 'Linear':
            # Linear interpolation from start to end CFG.
            current_segment_gs_to_use = initial_gs_from_ui + (distilled_cfg_end_value_for_schedule - initial_gs_from_ui) * progress

        elif variable_cfg_shape == 'Roll-off':
            # Roll-off logic adapted for per-segment scheduling.
            roll_off_start_point = roll_off_start / 100.0
            if progress < roll_off_start_point:
                current_segment_gs_to_use = initial_gs_from_ui
            else:
                # Avoid division by zero if roll_off_start_point is 1.0
                denominator = (1.0 - roll_off_start_point)
                if denominator > 0:
                    roll_off_progress = (progress - roll_off_start_point) / denominator
                    curved_progress = roll_off_progress ** roll_off_factor
                    current_segment_gs_to_use = initial_gs_from_ui + (distilled_cfg_end_value_for_schedule - initial_gs_from_ui) * curved_progress
                else:
                    # If roll_off_start_point is 1.0, we are at the end, use the end value.
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
    This function is designed to be used as a callback for a k-diffusion sampler.
    """
    current_diffusion_step = d["i"] + 1
    preview_latent = d["denoised"]
    # vae_decode_fake is a lightweight VAE decode for previews.
    preview_img_np = vae_decode_fake(preview_latent)
    preview_img_np = ((preview_img_np * 255.0).detach().cpu().numpy().clip(0, 255).astype(np.uint8))
    preview_img_np = einops.rearrange(preview_img_np, "b c t h w -> (b h) (t w) c")

    percentage = int(100.0 * current_diffusion_step / steps)
    hint = f"Segment {current_loop_segment_number}, Sampling {current_diffusion_step}/{steps}"
    current_video_frames_count = (history_pixels.shape[2] if history_pixels is not None else 0)
    desc = f"Task {task_id}: Vid Frames: {current_video_frames_count}, Len: {current_video_frames_count / fps :.2f}s. Seg {current_loop_segment_number}/{total_latent_sections}. Extending..."
    output_queue_ref.push(('progress', (task_id, preview_img_np, desc, make_progress_bar_html(percentage, hint))))

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
    This includes text encoding, VAE encoding of the initial image, and CLIP vision encoding.
    """
    if not high_vram:
        unload_complete_models()

    output_queue_ref.push(('progress', (task_id, None, f'Total Segments: {total_latent_sections}', make_progress_bar_html(0, "Text encoding ..."))))
    if not high_vram:
        fake_diffusers_current_device(text_encoder, gpu)
        load_model_as_complete(text_encoder_2, target_device=gpu)
    
    llama_vec, clip_l_pooler = encode_prompt_conds(prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)
    if real_cfg == 1:
        llama_vec_n, clip_l_pooler_n = torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)
    else:
        llama_vec_n, clip_l_pooler_n = encode_prompt_conds(negative_prompt, text_encoder, text_encoder_2, tokenizer, tokenizer_2)
    
    llama_vec, llama_attention_mask = crop_or_pad_yield_mask(llama_vec, length=512)
    llama_vec_n, llama_attention_mask_n = crop_or_pad_yield_mask(llama_vec_n, length=512)
    
    input_image_pt = (torch.from_numpy(input_image_np).float().permute(2, 0, 1).unsqueeze(0) / 127.5 - 1.0)
    input_image_pt = input_image_pt[:, :, None, :, :]
    
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

    # Ensure all tensors are on the correct dtype for the transformer
    for key, tensor in conditioning_tensors.items():
        if isinstance(tensor, torch.Tensor):
            conditioning_tensors[key] = tensor.to(transformer.dtype)
        
    return conditioning_tensors
