---
# Design Doc: CFG Scheduling and Roll-off

-   **Author**: Gemini
-   **Date**: 2025-07-03
-   **Status**: Implemented
-   **Replaces**: Design Doc: Contextual Damping for Initial Segment Generation

---

## 1. Summary

This document describes the implemented **CFG Scheduling and Roll-off** system, which was designed to fix the high-contrast artifact that can appear at the beginning of generated videos.

The solution is a flexible scheduling system that allows the CFG strength to be linearly interpolated from a starting value to an ending value over a user-defined portion of the generation process. This "roll-off" provides a smoother, more stable transition for the difficult "endcap" pass, which generates the video's beginning.

---

## 2. Problem

The FramePack architecture generates the beginning of the video last. This final "endcap" pass must create motion that connects the static input image (at time `t=0`) to the start of the already-generated video bulk.

With a high or steady CFG setting, this difficult task creates a contextual conflict for the model, resulting in unstable, high-contrast frames at the start of the final video output.

---

## 3. Implemented Solution

The application uses a flexible CFG scheduling mechanism to control guidance strength over the generation process. The primary schedule is a **"Linear Roll-off"**.

This system allows for stable generation during the bulk of the video, with a controlled, smooth transition for the difficult endcap pass. The mechanism works as follows:

1.  The user defines a `start_cfg` and an `end_cfg` value.
2.  The generation proceeds with the `start_cfg` value.
3.  At a user-defined `roll_off_start` percentage of the total segments, the system begins to linearly interpolate the CFG value.
4.  The CFG value gradually changes from `start_cfg` to `end_cfg`, reaching the `end_cfg` value at the final segment of the generation.

---

## 4. Implementation Details

The logic is implemented inside the main worker loop in `src/core/generation_core.py`. For each segment, it calculates the appropriate CFG value based on the user's settings before calling the sampler.

### UI Controls

The feature is exposed to the user through the following UI controls:
*   **`Distilled CFG Start`**: The initial CFG value used at the beginning of the generation.
*   **`Distilled CFG End`**: The final CFG value that the schedule will interpolate towards.
*   **`Roll-off Start (%)`**: The percentage of the way through the generation at which the linear interpolation should begin. A value of `0` starts the roll-off immediately, while `100` effectively disables it.

### Code

The following conceptual code block illustrates the logic inside the `worker` loop.

```python
            # --- CFG SCHEDULING LOGIC (Conceptual) ---
            # User-provided parameters from the UI
            start_cfg = params.get('distilled_cfg_start')
            end_cfg = params.get('distilled_cfg_end')
            roll_off_start_percent = params.get('roll_off_start_percent')
            total_segments = params.get('total_segments')

            # Inside the loop over segments (e.g., for i in range(total_segments):)
            current_segment_gs_to_use = start_cfg

            # Calculate the segment index where roll-off begins
            roll_off_start_segment = int(total_segments * (roll_off_start_percent / 100.0))

            if i >= roll_off_start_segment and total_segments > roll_off_start_segment:
                # Calculate progress through the roll-off phase (0.0 to 1.0)
                roll_off_duration = total_segments - 1 - roll_off_start_segment
                roll_off_progress = (i - roll_off_start_segment) / roll_off_duration if roll_off_duration > 0 else 1.0
                roll_off_progress = min(roll_off_progress, 1.0)

                # Linearly interpolate from start_cfg to end_cfg
                current_segment_gs_to_use = start_cfg * (1.0 - roll_off_progress) + end_cfg * roll_off_progress

            logger.info(f"Segment {i+1}/{total_segments}: Using scheduled CFG: {current_segment_gs_to_use:.2f}")

            generated_latents = sample_hunyuan(
                transformer=transformer,
                # ...
                distilled_guidance_scale=current_segment_gs_to_use,
                # ...
            )