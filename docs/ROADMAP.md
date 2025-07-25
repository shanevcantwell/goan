# Project Roadmap: `goan`

This document outlines the planned development milestones for `goan`. The goal is to provide a stable, powerful tool for creative professionals and to methodically build upon its foundation.

---

## **Milestone 1: Alpha 0.1 - The Stable Foundation (Released)**

**Primary Objective:** Release a bug-free, internally consistent version of `goan` that delivers a complete and reliable core user experience.

### Key Features & Requirements:

*   **Robust Queue Management:** (Weak implementation deprecated)
    *   Fully working queue controls: add, delete, and reorder tasks.
    *   Immediate and clear UI feedback for all button clicks.
    *   Graceful UI reconnection to a live backend service in a single-user context.

*   **Polished User Interface:**
    *   Continue tightening up the UI for clarity and intuitive workflow.
    *   Ensure the "Create Preview" button has reliable, context-aware interactivity.
    
## **Milestone 2: Alpha 0.2 - Polish & Reliability Hardening (In Progress)**

**Primary Objective:** Finalize the UI for a professional workflow and solidify the application's architecture for future expansion.

### Key Features & Requirements:
*   **"Handler-Returns-Dict" Architecture:** Completed a major internal refactor to decouple UI event logic from the UI layout. This eliminated a whole class of `ValueError` bugs, made the codebase significantly more robust and maintainable, and laid the groundwork for future feature expansion.
*   **UI Polish:** Finalizing UI layout, button interactivity, and overall workflow clarity.
*   **In-Queue Task Editing:**
    *   **Goal**: Allow a user to modify the parameters of a task already in the queue without needing to delete and recreate it.
    *   **Reference**: `DRAFT_feature_edit_task.md`

---

## **Milestone 3: Alpha 0.3 - Power User Features**

**Primary Objective:** Introduce features that significantly expand the creative and technical capabilities for advanced users.

### Key Features & Requirements:
*   **Full Task Pause & Resume:**
    *   Implement the full checkpointing and resumption logic as designed in `DRAFT_feature_resume.md`.
    *   This will allow a task to be gracefully paused and resumed later, or recovered after a crash from the last saved segment.
*   **Multi-LoRA Support:** Extend the UI and backend to support applying multiple LoRAs simultaneously.
*   **LoRA Metadata Portability (Phase 1):** Save and load a single LoRA's configuration (`name`, `weight`, `targets`) to/from PNG metadata.
*   **Compel Integration for Advanced Prompting:**
    *   **Goal**: Replace basic string prompting with the `Compel` library to support industry-standard syntax like token weighting `(word:1.2)` and prompt alternating `[word1|word2]`.
    *   **Reference**: `DRAFT_feature_compel.md`

---

## **Milestone 4: Future - Advanced Capabilities**

**Primary Objective:** Implement the "big idea" features that unlock new creative potential.

### Key Features & Requirements:
*   **Advanced LoRA Portability (Phase 2):** Implement the `source_url` logic and two-state UI for downloading missing LoRAs, as designed in `DRAFT_lora_support_just_raises_more_questions.md`.
*   **One-Click Seamless Looping:** Begin R&D and implementation of the advanced latent manipulation strategy outlined in `DRAFT_feature_one_click_looping.md` to allow for the creation of true, non-ping-pong video loops.

---

## **Milestone 5: Architectural Refactoring**

**Primary Objective:** Improve the application's scalability, security, and maintainability for long-term health and potential multi-user support.

### Key Features & Requirements:
*   **Phase 1: Session Management and Stateless Image Handling**
    *   **Goal**: Introduce session-level isolation for user queues and move from storing uploaded images on disk to handling them as in-memory Base64 strings.
    *   **Reference**: `DRAFT_feature_multiuser_image_handling.md`
*   **Phase 2: Secure, Temporary Video Serving**
    *   **Goal**: Stop writing generated videos to a public `outputs` folder. Instead, save them to a temporary, non-public location and serve them to the UI via short-lived, signed URLs.
    *   **Reference**: `DRAFT_feature_multiuser_image_handling.md`