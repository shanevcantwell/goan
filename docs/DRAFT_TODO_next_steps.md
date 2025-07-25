# Next Steps & Future Development TODO

This document outlines the planned features and architectural improvements for `goan`. It serves as a high-level roadmap, with detailed implementation strategies available in the respective design draft documents.

---

## 1. Core Feature Enhancements

These features will directly expand the creative capabilities of the application.

-   **[ ] Compel Integration for Advanced Prompting**
    -   **Goal**: Replace the basic string-based prompting with the `Compel` library to support industry-standard syntax like token weighting `(word:1.2)` and prompt alternating `[word1|word2]`.
    -   **Reference**: `DRAFT_feature_compel.md`

-   **[ ] Advanced Seamless Video Looping**
    -   **Goal**: Implement a "one-click" looping feature that uses latent manipulation and a refinement pass to create truly seamless, non-ping-pong video loops.
    -   **Reference**: `DRAFT_feature_one_click_looping.md`

-   **[ ] Task Checkpointing & Resumption**
    -   **Goal**: Allow users to recover from application crashes or intentional pauses without losing generation progress by saving and loading task state from `.goan_resume` files.
    -   **Reference**: `DRAFT_feature_resume.md`

---

## 2. UI/UX & Workflow Improvements

These items focus on improving the user experience and making creative workflows more efficient and portable.

-   **[ ] Portable LoRA Management & Metadata**
    -   **Goal**: Refactor LoRA handling to be URL-based rather than file-upload-based. Store LoRA configurations (name, weight, targets, source URL) in the output image's metadata to create fully portable "recipes".
    -   **Reference**: `DRAFT_lora_support_just_raises_more_questions.md`

---

## 3. Architectural Refactoring

These are major, long-term goals to improve the application's scalability, security, and maintainability.

-   **[ ] Phase 1: Session Management and Stateless Image Handling**
    -   **Goal**: Introduce session-level isolation for user queues and move from storing uploaded images on disk to handling them as in-memory Base64 strings. This is the first step towards multi-user support.
    -   **Reference**: `DRAFT_feature_multiuser_image_handling.md`

-   **[ ] Phase 2: Secure, Temporary Video Serving**
    -   **Goal**: Stop writing generated videos to a public `outputs` folder. Instead, save them to a temporary, non-public location and serve them to the UI via short-lived, signed URLs.
    -   **Reference**: `DRAFT_feature_multiuser_image_handling.md`