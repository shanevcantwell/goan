---
# Design Doc: In-UI LoRA Inspector

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-28
-   **Status**: Scratchpad / Low-Priority Idea
-   **Target Milestone**: Future (Post-Alpha)

---

## 1. Summary

This document outlines a potential future enhancement to integrate the existing command-line LoRA key inspector tool directly into the `goan` user interface. The goal is to provide users with a convenient, interactive way to analyze LoRA compatibility without leaving the application or using the terminal.

---

## 2. Problem

Currently, diagnosing why a specific LoRA file doesn't work as expected is a technical process. The developer-focused `lora_key_inspector.py` script is powerful but has significant drawbacks for the average user:

*   **High Friction**: It requires opening a terminal, navigating to the project directory, activating the virtual environment, and running a command with the correct file path. This completely breaks the creative workflow.
*   **Inaccessible**: It is not a user-friendly tool and is effectively inaccessible to users who are not comfortable with the command line.
*   **Poor Feedback Loop**: The user has to switch contexts (from the app to the terminal) to get information, then switch back to act on it.

---

## 3. Proposed Solution

The solution is to create a simple, non-intrusive inspection tool within the existing "LoRA" settings panel.

1.  **UI Integration**: Add an "Inspect a LoRA" `gr.UploadButton` to the "LoRA" settings panel.
2.  **Modal Display**: When a file is uploaded to this button, a modal window will appear to display the analysis report. This avoids cluttering the main UI.
3.  **Backend Handler**: A new event handler will receive the uploaded file. It will call the existing `lora_key_mapper.translate_and_analyze` function, which already contains all the necessary logic.
4.  **Formatted Report**: The handler will format the `report` dictionary returned by the analyzer into a human-readable format (e.g., using `gr.Markdown` with tables or `gr.DataFrame`) and display it in the modal.

This approach reuses the existing, robust backend logic while wrapping it in a simple and accessible UI.

---

## 4. Implementation Sketch

### 4.1. UI (`src/ui/layout.py`)

Within the "LoRA" settings group, add the inspector components.

```python
# In src/ui/layout.py, inside the lora_group

# ... existing LoRA upload controls ...
gr.Markdown("---") # Separator
components[K.LORA_INSPECT_BUTTON] = gr.UploadButton("🔍 Inspect a LoRA", file_types=[".safetensors"], size="sm")

# A new modal for the report
with Modal(visible=False) as lora_inspector_modal:
    components[K.LORA_INSPECTOR_MODAL] = lora_inspector_modal
    gr.Markdown("### LoRA Key Mapping Report")
    components[K.LORA_INSPECTOR_FILENAME] = gr.Markdown("")
    gr.Markdown("#### ✅ Mapped Keys")
    components[K.LORA_INSPECTOR_MAPPED_DF] = gr.DataFrame(headers=["LoRA Key", "Model Key"])
    gr.Markdown("#### ❌ Unmapped Keys")
    components[K.LORA_INSPECTOR_UNMAPPED_DF] = gr.DataFrame(headers=["LoRA Key", "Attempted Model Key"])
```

### 4.2. Handler (`src/ui/lora.py`)

A new handler function would be created to process the inspection request. It would call the existing `lora_key_mapper.translate_and_analyze` function and format the results for the `DataFrame` components in the modal.

### 4.3. Switchboard

The new `LORA_INSPECT_BUTTON` would be wired to the new handler, with its outputs targeting the components inside the `lora_inspector_modal`.

---

## 5. Priority

This is a **low-priority, quality-of-life** feature. It improves the user experience for power users but is not essential for the core functionality of the application. It should be considered for implementation after the primary Alpha milestones are complete.