# Project Roadmap: `goan`

This document outlines the planned development milestones for `goan`. The goal is to provide a stable, powerful tool for creative professionals and to methodically build upon its foundation.

---

## **Milestone 1: Alpha 0.1 - The Stable Foundation**

**Primary Objective:** Release a bug-free, internally consistent version of `goan` that delivers a complete and reliable core user experience. This version should be something that can be shared and used with confidence.

### Key Features & Requirements:

*   **Robust Queue Management:**
    *   Fully working queue controls: add, delete, reorder, and edit tasks.
    *   Immediate and clear UI feedback for all button clicks.
    *   Graceful UI reconnection to a live backend service in a single-user context.

*   **Polished User Interface:**
    *   Continue tightening up the UI for clarity and intuitive workflow.
    *   Ensure the "Create Preview" button has reliable, context-aware interactivity.

*   **"Local" LoRA Recipes (New Feature):**
    *   **Save Logic:** When a user clicks "Download Image," the application will save the currently used LoRA's `name`, `weight`, and `target modules` into the PNG metadata.
    *   **Load Logic:** When a user drops a PNG with this metadata, the UI will read it and attempt to apply the settings, assuming the user has the correctly named LoRA file locally.
    *   **Schema:** The metadata will use a future-proof `loras: [{...}]` list-based schema, but this initial implementation will only read/write the first element.

### Explicitly Out of Scope for Alpha 0.1:

*   **Task Pause/Resume:** The "Pause" buttons in the UI will be present but disabled. Full checkpointing and resumption is deferred.
*   **Portable LoRA Recipes:** The more advanced implementation with `source_url` handling and in-app LoRA downloading is deferred.
*   **One-Click Seamless Looping:** The advanced latent manipulation feature is a major R&D effort planned for a future release.

---

## **Milestone 2: Post-Alpha - Core Reliability & Power Features**

**Primary Objective:** Deliver on the high-value reliability and power-user features promised in the `README.md` and design documents.

### Key Features:

*   **Full Task Pause & Resume:**
    *   Implement the full checkpointing and resumption logic as designed in `DRAFT_feature_resume.md`.
    *   This will allow a task to be gracefully paused and resumed later, or recovered after a crash from the last saved segment.

*   **Portable LoRA Recipes:**
    *   Implement the full vision from `DRAFT_lora_support_just_raises_more_questions.md`.
    *   Extend the metadata schema to include a `source_url`.
    *   Implement the two-state UI that shows a "Download" button for missing LoRAs that have a source URL.
    *   Build the downloader logic with the critical user-confirmation step.

---

## **Milestone 3: Future - Advanced Capabilities**

**Primary Objective:** Implement the "big idea" features that unlock new creative potential.

### Key Features:

*   **Multi-LoRA Support:** Refactor the UI and backend to support applying and managing multiple LoRAs simultaneously, fulfilling the promise of the list-based metadata schema.
*   **One-Click Seamless Looping:** Begin R&D and implementation of the advanced latent manipulation strategy outlined in `DRAFT_feature_one_click_looping.md` to allow for the creation of true, non-ping-pong video loops.