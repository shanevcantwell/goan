# Design Doc: Multi-User Architecture and Stateless I/O

-   **Author**: Gemini Code Assist
-   **Date**: 2025-07-06
-   **Status**: Proposed

---

## 1. Summary

This document outlines a phased approach to refactor the application for true multi-user support. The primary architectural goals are to introduce session-level isolation for user queues and to eliminate the persistent storage of user-provided or user-generated files on the server's local filesystem. This will be achieved by moving to in-memory Base64 encoding for uploaded images and implementing a secure, temporary serving mechanism for generated videos, paving the way for future integration with user-owned cloud storage.

---

## 2. Problem

The current architecture has several limitations that prevent safe and scalable multi-user deployment:

*   **Singleton State:** Core components like `QueueManager` are singletons, meaning all users would share a single global task queue, leading to data collision and privacy issues.
*   **Server-Side File Persistence:**
    *   **Uploaded Images:** The `save_queue` and `autosave` features write uploaded source images to the server's filesystem (either in a temp directory or a user-downloadable zip). This is a security and data management liability.
    *   **Generated Videos:** The `worker` process writes all generated MP4 files directly to a local `outputs` folder. This is not scalable and poses a significant data privacy risk in a multi-user environment.
*   **Session Unawareness:** The application lacks a formal session management system, relying on process IDs for autosave, which is insufficient for robust user isolation.

---

## 3. Proposed Solution

The solution is a two-phased implementation focusing on sessionization and stateless I/O.

### Phase 1: Session Management and Stateless Image Handling

This phase establishes the foundational architecture for user isolation.

1.  **Session ID Management:**
    *   On a user's first connection, the server will generate a unique `session_id` (e.g., a UUID).
    *   This `session_id` will be sent to the client and stored in the browser's `localStorage` or a cookie.
    *   Every subsequent request from the client to the Gradio backend will need to include this `session_id`.

2.  **Session-Aware State Management:**
    *   Refactor `QueueManager` from a singleton to a factory or a dictionary-based manager. A central registry will hold `QueueManager` instances, keyed by `session_id`.
    *   All queue operations (`add_task`, `get_state`, etc.) will require a `session_id` to operate on the correct user's queue.

3.  **Base64 Image Encoding:**
    *   When a user adds a task, the `input_image` (PIL/NumPy) will be immediately converted to a Base64 data URI string.
    *   This string, not the raw binary data, will be stored in the task's parameters within the user's session-specific queue.
    *   The `worker` process will be updated to accept this Base64 string, decode it back into a NumPy array in memory, and then proceed with generation.
    *   This eliminates the need to write uploaded images to disk for `save_queue` or `autosave` operations. The downloaded/autosaved queue will simply be a JSON file containing these Base64 strings.

### Phase 2: Secure, Temporary Serving of Generated Videos

This phase addresses the challenge of handling large, generated video files without permanent server-side storage.

1.  **Secure Temporary Storage:**
    *   The `worker` will no longer save files to the static `./outputs` directory.
    *   A new, non-public directory (e.g., `/var/goan_temp_renders` or a system temp directory) will be used for temporary storage.
    *   Generated files will be saved with random, unguessable UUID-based filenames (e.g., `f47ac10b-58cc-4372-a567-0e02b2c3d479.mp4`).

2.  **Time-Limited, Signed URLs:**
    *   When a video is generated, the `ProcessingAgent` will receive the path to the temporary file.
    *   The agent will request a short-lived, signed URL from a new `URLSigningService`. This service will generate a URL with a token and an expiration timestamp (e.g., valid for 1 hour).
    *   This secure URL, not the direct file path, will be sent to the user's UI.
    *   The `gr.Video` component will load the video directly from this URL. This prevents direct access to the server's filesystem and enumeration attacks.

3.  **Automatic Cleanup:**
    *   A periodic background task (e.g., a cron job or a `threading.Timer` loop) will run on the server.
    *   This task will scan the temporary storage directory and delete any files older than a configured retention period (e.g., 24 hours), ensuring the server does not accumulate orphaned files.

---

## 4. Future Work: Direct-to-Cloud Integration

While Phase 2 provides a robust and secure solution, the ultimate "zero-trust" architecture would involve direct integration with user-owned cloud storage.

*   **OAuth2 Integration:** Implement an OAuth2 flow to allow users to connect their Google Drive, Dropbox, or S3-compatible accounts.
*   **Direct-to-Cloud Worker:** The `worker` process would use the authenticated user's credentials (access tokens) and the respective cloud provider's SDK to stream the generated MP4 file directly to the user's storage bucket/folder, bypassing the server's local disk entirely.

This approach offers the highest level of security and scalability but represents a significant increase in implementation complexity and will be considered for a future major version.
