---
# Design Doc: Compel Integration for Advanced Prompting

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-12
-   **Status**: Proposed

---

## 1. Summary

This document proposes the integration of the [Compel](https://github.com/damian0815/compel) library to replace the current basic prompt processing system. The goal is to enable advanced prompt syntax, such as token weighting `(word:1.2)`, prompt alternating `[word1|word2]`, and other community-standard features that allow for fine-grained artistic control over the generation process.

---

## 2. Problem

Currently, the application treats the positive and negative prompt fields as literal strings. This approach is simple and reliable but lacks the expressive power that artists have come to expect from modern generative AI tools. Key features that are standard in other UIs are unavailable:

-   **Token Weighting**: Increasing or decreasing the emphasis of specific words or phrases (e.g., `a (blue:1.3) car`).
-   **Prompt Blending/Alternating**: Scheduling different concepts to appear at different steps in the diffusion process.
-   **Escape Characters**: Inability to properly handle special characters that are part of the prompt syntax.

This limitation restricts creative control and makes it difficult to port or replicate complex prompts from other platforms.

---

## 3. Proposed Solution

We will integrate the Compel library to handle all prompt parsing and conditioning.

1.  **Dependency**: Add `compel` as a project dependency.
2.  **Integration Point**: The integration will occur within the `worker` function in `src/core/generation_core.py`, just before the main generation loop begins.
3.  **Workflow**:
    -   Inside the `worker`, an instance of `Compel` will be created, initialized with the application's text encoders and tokenizer.
    -   The positive and negative prompt strings from the task parameters will be passed to Compel's `build_conditioning_tensor` method.
    -   Compel will parse the syntax and return the final `conditioned_embeddings` and `unconditioned_embeddings` tensors.
    -   These tensors will then be used as the `prompt_embeds` and `negative_prompt_embeds` for the duration of the generation task, replacing the direct text-to-embedding logic currently in place.

---

## 4. Historical Context & Implementation Notes

An attempt to implement this feature was made very early in the project's history. It proved to be surprisingly difficult at the time, likely due to challenges in correctly integrating Compel with the Hunyuan model's specific text encoder architecture or potential environment conflicts.

A review of the early git history is recommended, as a partially or fully working solution may exist that can be used as a reference. The key challenge will be ensuring that the `Compel` object is instantiated with the correct model components and that the output tensors are correctly shaped and typed for the `HunyuanDiT` transformer.

---

## 5. Benefits

-   **Unlocks Advanced Artistry**: Provides users with powerful, industry-standard tools for prompt engineering.
-   **Improves Compatibility**: Allows users to seamlessly use prompts and techniques from other popular platforms like Automatic1111 and ComfyUI.
-   **Simplifies Code**: Offloads the complexity of prompt parsing to a dedicated, well-maintained library, simplifying the core generation logic.

---

## 6. Risks

-   **Integration Complexity**: As noted, this has been challenging before. Careful debugging will be needed to ensure the text encoders are passed to Compel correctly.
-   **Dependency Conflicts**: The `compel` library may have dependencies that conflict with the current environment. This will need to be verified.