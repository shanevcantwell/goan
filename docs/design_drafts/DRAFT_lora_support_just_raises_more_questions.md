---
# Design Doc: LoRA Configuration in Image Metadata

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-10
-   **Status**: Proposed

---

## 1. Summary

This document proposes extending the application's PNG metadata system to include LoRA configurations. The goal is to save which LoRAs, weights, and model targets were used for a generation directly into the output image file. This makes an artist's creative "recipe" fully self-contained and allows for one-click recall of complex LoRA setups from a single image.

---

## 2. Problem

Currently, an image generated using one or more LoRAs contains no record of them in its metadata. An artist can save the prompt, seed, and other settings, but the crucial information about the applied LoRAs is lost.

This limitation hinders reproducibility and collaboration. If an artist wants to recreate or build upon a previous work, they must manually remember and re-configure the exact LoRA setup, which is error-prone and inefficient. The "recipe" is incomplete.

---

## 3. Proposed Solution

We will enhance the existing metadata save/load workflow to be LoRA-aware.

1.  **Extend Metadata Schema:** A new `loras` key will be added to the `parameters` JSON object that is saved into the PNG's `tEXt` chunk. This key will hold a list of objects, where each object details a single applied LoRA. This list-based schema is future-proof for a multi-LoRA system.

2.  **Update Save Logic:** The `prepare_image_for_download` handler will be modified. It will now read the current state of the LoRA UI controls and embed the configuration into the `params_dict` before it's written to the image.

3.  **Update Load Logic:** A new handler, `load_lora_settings_from_metadata`, will be created. When a user drops an image and confirms they want to apply its settings, this new handler will be called. It will parse the `loras` key from the metadata and automatically populate the LoRA UI controls, making the specific LoRA setup instantly active.

---

## 4. Implementation Details

### 4.1. New Metadata Schema

The `loras` key will contain a list of LoRA configuration objects. For the current single-LoRA UI, this list will contain at most one element.

```json
"parameters": {
    "prompt": "a beautiful landscape",
    "seed": 12345,
    "...": "...",
    "loras": [
        {
            "name": "MyCharacterV2.safetensors",
            "weight": 0.75,
            "targets": ["transformer", "text_encoder"]
        }
    ]
}
```

### 4.2. Code Implementation

*   **`src/ui/event_handlers.py`**: The `prepare_image_for_download` function's signature and logic will be updated to accept and process values from the LoRA UI controls.
*   **`src/ui/lora.py`**: A new handler function, `load_lora_settings_from_metadata`, will be added to parse the metadata and return `gr.update()` objects for the LoRA UI.
*   **`src/ui/switchboard_image.py`**: The event wiring for the `DOWNLOAD_IMAGE_BUTTON` and `CONFIRM_METADATA_BUTTON` will be modified to pass the necessary inputs and chain the new LoRA loading handler.

---

## 6. A Pragmatic Approach to LoRA Portability and Management

You've raised an excellent point: building a bespoke file manager UI is complex and unnecessary for a single-user application. Instead of managing local files with a complex CRUD interface, we will adopt a more pragmatic approach focused on making creative recipes truly portable.

### 6.1. The Problem with Local File Management

The current "Upload a LoRA" feature encourages a workflow where users manually download and manage files. This is brittle and creates several issues:
-   **Broken Portability**: Sharing an image with metadata `name: "style.safetensors"` is useless if the recipient doesn't have that exact file.
-   **Workspace Clutter**: The local `./loras` directory becomes an unmanaged cache of files with no clear provenance.
-   **High Friction**: The burden of finding and managing files is placed entirely on the user, breaking the creative flow.

### 6.2. Proposed Solution: Two-State UI with User-Initiated Downloads

We will pivot away from the "upload-and-forget" model. The `./loras` folder will be treated as a managed cache, and the UI will intelligently handle two states for any given LoRA: **metadata-only** and **locally available**.

1.  **URL as the Source of Truth**: The primary way to add a *new* LoRA to the system will be by providing a URL. The "Upload File" button will be deprecated. The `source_url` will be stored in the image metadata as the canonical identifier for that LoRA.

2.  **Truly Portable Recipes via a Two-State UI**: When a user loads an image with LoRA metadata:
    *   `goan` reads the LoRA `name` and `source_url` from the metadata.
    *   It checks if a file with that `name` exists in the `./loras` cache.
    *   **State 1 (File Missing)**: If the file is not found, the UI will indicate that the LoRA is required but not installed. If a `source_url` is present, a "Download" button will appear next to the missing LoRA's name. This makes the recipe immediately actionable.
    *   **State 2 (File Present)**: If the file is found, the UI will automatically select it in the dropdown and apply the weight and target settings from the metadata.

3.  **User-Initiated, Confirmed Downloads**: The application will **never** automatically download a file. When the user clicks the "Download" button for a missing LoRA, a confirmation prompt will appear, showing the full URL and asking for explicit permission. This puts the user in control and mitigates the risk of downloading from an untrusted source.

    ```json
    "loras": [
        {
            "name": "MyCharacterV2.safetensors",
            "weight": 0.75,
            "targets": ["transformer", "text_encoder"],
            "source_url": "https://huggingface.co/user/repo/blob/main/MyCharacterV2.safetensors"
        }
    ]
    ```

4.  **API Key Management (Future)**: To support sources like Civitai, which may require authentication, a section in the settings can be added later for users to provide an API key.

### 6.3. The Single vs. Multi-LoRA Discrepancy

**Problem**: The `DEVELOPERS_GUIDE.md` describes a multi-LoRA architecture, but the current implementation in `switchboard_queue.py` and `agents.py` is hardwired to handle only a single LoRA.

**Decision**: This metadata design will adhere to the list-based schema (`"loras": [...]`) to remain future-proof. However, the initial implementation of the save/load logic will only process the first element of the list, matching the current single-LoRA capability of the UI. This ensures the feature works now while being ready for a future multi-LoRA UI refactor without requiring a breaking change to the metadata format.

---

## 5. Security, Trust, and User Guidance

### 5.1. The "Third-Party Binary" Problem

A critical consideration is that LoRA files are model weights downloaded from third-party sources. While the `.safetensors` format is designed to be secure against arbitrary code execution (unlike Python's `pickle` format), the application must still treat these files as untrusted external dependencies.

The risks include:
-   **Model Integrity**: A poorly trained or malicious LoRA could be designed to produce unexpected, unstable, or offensive content.
-   **Provenance**: Without a management system, it's difficult for users to track where a LoRA came from, what it's for, or if it's the correct version.
-   **User Experience Friction**: When sharing a "recipe" (an image with metadata), the recipient is left to manually hunt for the required LoRA files, which can be a significant barrier.

### 5.2. Proposed Enhancements

To address these issues, the LoRA metadata feature will be implemented with the following user-facing safeguards and guidance:

1.  **Explicit UI Disclaimer**: A permanent, non-intrusive disclaimer will be added to the LoRA UI section:
    > "⚠️ **Note**: LoRA files are third-party models. Only use files from trusted sources like Civitai or Hugging Face."

2.  **Smarter "Missing LoRA" Feedback**: When loading metadata for a LoRA that is not present, the application will provide more actionable feedback than a simple "file not found" warning.
    *   **Previous Warning**: `Warning: LoRA 'MyCharacterV2.safetensors' from image metadata not found.`
    *   **Proposed Enhanced UI**: A UI element indicating the LoRA is missing, with a "Download" button if a `source_url` is available.

### 5.3. The "Untrusted URL" Problem and User Confirmation

You've raised a critical point: platforms like Hugging Face allow anyone to create and upload models. Therefore, a `source_url` in metadata cannot be implicitly trusted. The risk is not arbitrary code execution (thanks to `.safetensors`), but one of model integrity or downloading an unwanted file.

To mitigate this, the application will **never automatically download a file without explicit user consent**. The "Download" button in the UI will always trigger a confirmation step, ensuring the user is aware of the source and gives final approval.

---