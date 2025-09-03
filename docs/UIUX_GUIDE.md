# Goan UI/UX Integration Guide

## 1. Introduction & Core Philosophy

This document serves as a guide for frontend developers building user interfaces against the `goan` FastAPI backend. The application has transitioned from a monolithic Gradio UI to a decoupled, API-first architecture.

The original UI, defined in `ui/layout.py`, was not merely a collection of controls; it represented a specific user experience and workflow. This guide extracts the *semantic meaning* of that layout and maps it to the new Pydantic API schemas to ensure that new UIs can be built with a consistent and intuitive user experience.

The core concept of the `goan` workflow is the **"Recipe"**. A recipe consists of an input image combined with a set of creative and technical parameters that define a generation task. In the new architecture, this recipe is formally defined by the `TaskParams` Pydantic model.

## 2. Mapping UI Concepts to the `TaskParams` Schema

The original Gradio UI organized dozens of controls into logical groups. A new UI should honor these groupings to maintain usability. The primary data model for submitting a task is `TaskParams` from `api/pydantic_models.py`.

### 2.1. Core Creative Parameters

These are the most fundamental inputs for a task, equivalent to the top-level controls in the original UI.

| UI Concept | `TaskParams` Field | Description |
| :--- | :--- | :--- |
| Prompt | `prompt` | The main positive text prompt for the generation. |
| Negative Prompt | `negative_prompt` | The negative text prompt. |
| Seed | `seed` | The random seed for the generation. `-1` for random. |
| Video Length | `video_length` | The desired output video length in seconds. |
| Input Image | (multipart/form-data) | The source image for the I2V task. Submitted alongside `TaskParams`. |

### 2.2. Power User Parameters (CFG & Steps)

This group contains the primary controls for fine-tuning the generation process. In the original UI, these were grouped under the "Power User" collapsible menu.

| UI Concept | `TaskParams` Field | Description |
| :--- | :--- | :--- |
| Steps | `steps` | The number of diffusion steps per segment. |
| CFG (Real) | `real_cfg` | The guidance scale for the "real" (non-distilled) CFG. |
| Variable CFG Shape | `variable_cfg_shape` | Controls the CFG schedule. Can be `"Off"`, `"Linear"`, or `"Roll-off"`. |
| Distilled CFG Start | `distilled_cfg_start` | The starting guidance scale for the distilled CFG. |
| Distilled CFG End | `distilled_cfg_end` | The ending guidance scale when `variable_cfg_shape` is not `"Off"`. |
| Roll-off Start % | `roll_off_start` | The percentage of the timeline at which the CFG roll-off begins. |
| Roll-off Curve Factor | `roll_off_factor` | The exponent for the roll-off curve, controlling its steepness. |
| Guidance Rescale (RS) | `guidance_rescale` | The guidance rescale value. |

### 2.3. Advanced & Technical Parameters

These parameters, originally in the "Advanced" menu, control the technical aspects of the generation and output format. They are generally "set and forget" for most users.

| UI Concept | `TaskParams` Field | Description |
| :--- | :--- | :--- |
| MP4 Framerate (FPS) | `fps` | The frames-per-second of the final output video. |
| MP4 CRF | `mp4_crf` | The Constant Rate Factor for MP4 encoding (lower is higher quality). |
| Latent Window Size | `latent_window_size` | The size of the latent window used during generation. |
| Use TeaCache | `use_teacache` | A performance optimization for the transformer model. |
| Use FP32 Transformer | `use_fp32_transformer_output` | Forces FP32 precision for stability on older GPUs. |
| GPU Preserve (GB) | `gpu_memory_preservation` | VRAM to reserve in low-VRAM mode. |
| Output Folder | `output_folder` | The directory on the server where outputs will be saved. |

### 2.4. Preview & Monitoring Parameters

These controls allow the user to specify how and when intermediate previews are generated during a long task.

| UI Concept | `TaskParams` Field | Description |
| :--- | :--- | :--- |
| Preview Interval | `preview_frequency` | Generate a preview MP4 every N segments. `0` to disable. |
| Preview Segments | `preview_specified_segments` | A comma-separated string of specific segment numbers to preview (e.g., "3,5,10"). |

## 3. LoRA Application (`LoraControls` Schema)

In the `goan` architecture, LoRA settings are **not** part of an individual task's recipe. Instead, a single LoRA configuration is applied to an entire queue processing run. This is a critical distinction for UI design.

The `LoraControls` Pydantic model defines this configuration.

| UI Concept | `LoraControls` Field | Description |
| :--- | :--- | :--- |
| LoRA Name | `lora_name` | The filename of the LoRA to apply (e.g., `MyLora.safetensors`). |
| Weight | `lora_weight` | The weight at which to apply the LoRA. |
| Target Models | `lora_targets` | A list of model components to apply the LoRA to (e.g., `["transformer", "text_encoder"]`). |

## 4. Core User Workflows via API

A frontend application must orchestrate API calls to replicate the user workflows of the original UI.

### Workflow 1: Creating and Adding a Task

This workflow corresponds to filling out the UI and clicking the "Add to Queue" button.

1.  The client UI collects all parameter values from the user.
2.  The client constructs a JSON object matching the `TaskParams` schema.
3.  The client takes the user's uploaded image.
4.  The client sends a `multipart/form-data` **`POST`** request to the `/api/tasks` endpoint, with the `TaskParams` JSON as one part and the image file as another.

### Workflow 2: Starting the Generation Process

This corresponds to clicking the "Process Queue" button.

1.  The client UI collects the LoRA settings from the user.
2.  The client constructs a JSON object matching the `LoraControls` schema.
3.  The client sends a **`POST`** request with this JSON body to the `/api/processing/start` endpoint.

### Workflow 3: Monitoring Progress and State

This replaces the complex `yield`-based updates of the Gradio UI.

1.  **Queue State:** To display the list of tasks, the client sends a **`GET`** request to `/api/queue`. The response will match the `QueueState` schema, which can be used to render the task list. This should be polled periodically to reflect changes (like task status updates).
2.  **Real-time Progress:** For real-time updates during processing, the client must connect to the **`/api/stream`** Server-Sent Events (SSE) endpoint.
    *   The client will receive messages in the format `data: {"event": "EVENT_TYPE", "data": {...}}`.
    *   The `event` key will correspond to a `UIMessage` enum value (e.g., `PROGRESS`, `FILE`, `END`).
    *   The `data` payload will contain progress bar information, preview images (as base64 strings, if implemented), and file paths, which the UI can use to update itself without polling.

### Workflow 4: Loading a Recipe from an Image

The original UI could automatically load settings from a previously generated PNG file. This workflow is now primarily a client-side responsibility.

1.  A user uploads a PNG file to the client application.
2.  The client application must inspect the PNG's metadata for the `goan_params` key (as described in `DEVELOPERS_GUIDE.md`). This may require a client-side library or a dedicated helper endpoint on the backend (e.g., `/api/image/extract-metadata`).
3.  The client parses the JSON string found in the metadata.
4.  The client uses the parsed data to populate its own UI form fields, effectively loading the recipe for the user.
5.  From here, the user can modify the loaded recipe and proceed with **Workflow 1** to add it as a new task.
