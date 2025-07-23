# Project Roadmap: `goan`

This document outlines the planned development milestones for `goan`. The goal is to provide a stable, powerful tool for creative professionals and to methodically build upon its foundation.

---

## **Milestone 1: Alpha 0.1 - The Stable Foundation (Released)**

**Primary Objective:** Release a bug-free, internally consistent version of `goan` that delivers a complete and reliable core user experience.

### Key Features & Requirements:

*   **Robust Queue Management:** (Weak implementation deprecated)
    *   Fully working queue controls: add, delete, reorder, and edit tasks.
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

---

## **Milestone 3: Alpha 0.3 - Power User Features**

*   **Full Task Pause & Resume:**
    *   Implement the full checkpointing and resumption logic as designed in `DRAFT_feature_resume.md`.
    *   This will allow a task to be gracefully paused and resumed later, or recovered after a crash from the last saved segment.
*   **Multi-LoRA Support:** Extend the UI and backend to support applying multiple LoRAs simultaneously.
*   **LoRA Metadata Portability (Phase 1):** Save and load a single LoRA's configuration (`name`, `weight`, `targets`) to/from PNG metadata.

---

## **Milestone 4: Future - Advanced Capabilities**

**Primary Objective:** Implement the "big idea" features that unlock new creative potential.

### Key Features:
*   **Advanced LoRA Portability (Phase 2):** Implement the `source_url` logic and two-state UI for downloading missing LoRAs, as designed in `DRAFT_lora_support_just_raises_more_questions.md`.
*   **One-Click Seamless Looping:** Begin R&D and implementation of the advanced latent manipulation strategy outlined in `DRAFT_feature_one_click_looping.md` to allow for the creation of true, non-ping-pong video loops.