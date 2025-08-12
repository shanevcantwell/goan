# src/ui/css_main.py
# This file contains the main/global CSS for the Gradio application.
# It also imports and combines panel-specific CSS.

from .css_top_panel import CSS_TOP_PANEL
from .css_bottom_panel import CSS_BOTTOM_PANEL

CSS_MAIN = """
/* --- Global Layout & Style Adjustments --- */
/* Remove all gaps between components in rows, columns, and forms for a flush layout */
.gradio-container .gr-row, .gradio-container .gr-column, .gradio-container .gr-form {
    gap: 0 !important;
}

/* --- Global Button Styling --- */
/* Give all buttons a subtle, consistent border and remove the default shadow. */
.gr-button {
    border: 1px solid var(--border-color-primary) !important;
    box-shadow: none !important;
}

/* --- NEW: Utility Class for Flat Inputs (T02) --- */
/* Removes default styling from textboxes and other inputs for a seamless look. */
.flat-input {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
/* Target the inner textarea element specifically, as it often has its own border. */
.flat-input textarea {
    background-color: transparent !important;
}
/* Target the image component's inner wrapper to remove its border. */
.flat-input > div[data-testid="image"] {
    border: none !important;
}

/* NEW: Compact Row for Sliders and HTML */
.compact-row > * {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

.compact-row .gr-html {
    min-height: unset !important; /* Remove any minimum height */
    line-height: 1.2em !important; /* Adjust line height for text */
}

.compact-row .gradio-slider {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

/* NEW: Compact Group for Power User Menu */
.compact-group {
    padding: 0 !important;
    margin: 0 !important;
}

.compact-group > * {
    padding: 0 !important;
    margin: 0 !important;
}

/* --- Connected Button Group Styling --- */
/* Creates a visually connected group of buttons in a row. Applied via elem_classes="button-group". */
/* This new approach gives the container the border and removes it from the inner buttons,
   which prevents the "beveled" look from individual button borders. */
.button-group {
    gap: 0 !important;
    /* Add a border to the container itself. */
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 0 !important; /* Squared off to match the top panel style */
    /* Hide overflow to ensure inner button corners are sharp and contained. */
    overflow: hidden;
}

/* --- DEFINITIVE FIX FOR T06 (Inspector-based) --- */
/* Hide the component's label, which is a span with a specific data-testid */
#settings_menu_checkbox_group span[data-testid="block-info"] {
    display: none !important;
}
/* Remove the border from the fieldset itself, which has both the ID and the class */
fieldset#settings_menu_checkbox_group.button-group {
    border: none !important;
}

#queue_df { font-size: 0.9rem; }

/* --- Task Queue Column Styling (T03) --- */
/* Use a fixed table layout to enforce column widths accurately. */
#queue_df table {
    /* Removed table-layout: fixed; to allow columns to size based on content */
    width: 100%;
    border-collapse: collapse; /* Ensures borders are clean */
}

/* Default for all headers/cells: vertical alignment and a subtle bottom border. */
#queue_df th, #queue_df td {
    vertical-align: middle;
    padding: 4px 8px;
    border: none; /* Remove all default borders */
    border-bottom: 1px solid var(--border-color-primary); /* Add a subtle separator */
}

/* Style the header row for emphasis */
#queue_df th {
    font-weight: bold;
    background-color: #2a313f; /* Slightly lighter than the main background */
}

/* --- NEW: Scrollable Prompt Cell (T03) --- */
/* This allows long prompts in the queue to be scrollable instead of taking up excess vertical space. */
.prompt-cell-scrollable {
    max-height: 5em; /* Sets a max height */
    overflow-y: auto; /* Adds a scrollbar only when content overflows */
    white-space: pre-wrap; /* Respects newlines and spaces within the prompt */
    word-break: break-word; /* Prevents long words from breaking the layout */
    text-align: left; /* Ensures text is aligned left for readability */
    padding-right: 5px; /* Adds a small gap between text and the scrollbar */
}

/* --- Fix for Queue Action Click Targets --- */
/* Make the entire cell for an action icon a clickable link, improving hit area. */
#queue_df td:nth-child(-n+5) a {
    display: block;
    padding: 4px 2px; /* This padding defines the clickable area inside the link. */
    line-height: 1.5; /* Improve vertical spacing and click target height. */
}
/* Disable clicks on the disabled action icons (spans) */
#queue_df td:nth-child(-n+5) span {
    pointer-events: none;
}
/* Disable the annoying drag behavior on links and images in the queue */
#queue_df a, #queue_df img {
    -webkit-user-drag: none; user-drag: none;
    user-select: none; -webkit-user-select: none; -moz-user-select: none;
}

/* Status Column (1): Shrink to content, left-aligned, allows wrapping. */
#queue_df th:nth-child(1), #queue_df td:nth-child(1) {
    min-width: 10rem; /* Ensure enough space for status messages like "Processing" */
    text-align: left;
    white-space: normal; /* Allow text to wrap */
}

/* Prompt Column (2): Takes up remaining space, left-aligned. */
#queue_df th:nth-child(2), #queue_df td:nth-child(2) {
    text-align: left;
    width: 100%; /* Take up all available space */
}

/* Image (3), Length (4), ID (5) Columns: Shrink to content, centered. */
#queue_df th:nth-child(3), #queue_df td:nth-child(3) { width: auto; text-align: center; }
#queue_df th:nth-child(4), #queue_df td:nth-child(4) { width: auto; text-align: center; }
#queue_df th:nth-child(5), #queue_df td:nth-child(5) { width: auto; text-align: center; }

.gradio-container { max-width: 95% !important; margin: auto !important; }
:root {
    /*
       Color-blindness consideration: The current palette uses green (accent) and red (stop variant)
       which can be problematic for deuteranopia/protanopia. The UI mitigates this by using
       text and icons (▶️, ⏹️) as primary indicators, which is a good practice. Future color revisions
       should consider palettes that rely on hue and brightness differences that are more universally
       distinguishable (e.g., using blue/orange instead of green/red).
    */
    --color-accent-soft: #4CAF50; --color-accent-50: #e8f5e9;
    --color-accent-100: #c8e6c9; --color-accent-200: #a5d6a7;
    --color-accent-300: #81c784; --color-accent-400: #66bb6a;
    --color-accent-500: #4CAF50; --color-accent-600: #43A047;
    --color-accent-700: #388E3C; --color-accent-800: #2E7D32;
    --color-accent-900: #1B5E20;
}
/* Apply green color only to *enabled* primary buttons to allow default disabled styles. */
.gr-button-primary:not([disabled]) { background-color: var(--color-accent-500) !important; color: white !important; }
.gr-button-primary:not([disabled]):hover { background-color: var(--color-accent-600) !important; }

/* Custom blue color for specific action buttons (T05) */
#clear_image_button:not([disabled]), #download_image_button:not([disabled]) {
    background-color: #2563eb !important; /* A darker, less intense blue (Tailwind blue-600) */
    color: white !important;
}
#clear_image_button:not([disabled]):hover, #download_image_button:not([disabled]):hover {
    background-color: #1d4ed8 !important; /* A slightly darker blue for hover (Tailwind blue-700) */
}

/* --- Consistent Disabled Button Styling --- */
/* This ensures all buttons, regardless of their original color, have the same greyed-out appearance when disabled. */
.gr-button-primary[disabled],
.gr-button-stop[disabled],
#clear_image_button[disabled],
#download_image_button[disabled] {
    background-color: #374151 !important; /* Dark grey for dark theme */
    color: #9ca3af !important;            /* Muted grey for text */
    border-color: #4b5563 !important;     /* Slightly lighter border */
}

/* --- NEW: Standardized Button Styles (T05) --- */
/* Muted Blue for Image Buttons */
.muted-blue-button {
    background-color: #2563eb !important; /* Tailwind blue-600 */
    color: white !important;
}
.muted-blue-button:hover {
    background-color: #1d4ed8 !important; /* Tailwind blue-700 */
}

/* Primary Button (Orange) */
.primary-button {
    background-color: #f97316 !important; /* Tailwind orange-500 */
    color: white !important;
}
.primary-button:hover {
    background-color: #ea580c !important; /* Tailwind orange-600 */
}

/* Secondary Button (Dark Gray/Outline) */
.secondary-button {
    background-color: #374151 !important; /* Tailwind gray-700 */
    color: #d1d5db !important; /* Tailwind gray-300 */
    border: 1px solid #4b5563 !important; /* Tailwind gray-600 */
}
.secondary-button:hover {
    background-color: #4b5563 !important; /* Tailwind gray-600 */
}

/* Destructive Button (Red) */
.destructive-button {
    background-color: #ef4444 !important; /* Tailwind red-500 */
    color: white !important;
}
.destructive-button:hover {
    background-color: #dc2626 !important; /* Tailwind red-600 */
}

/* --- NEW, MORE ROBUST FIX for fullscreen images --- */
/* This targets any image inside a fixed-position container, which is
   how Gradio implements the fullscreen view. Using a space instead of '>'
   makes it work even if the image is nested inside other divs. */
div.fixed img {
    width: auto !important;
    height: auto !important;
    max-width: 95vw !important;  /* Max width is 95% of the viewport width */
    max-height: 95vh !important; /* Max height is 95% of the viewport height */
    object-fit: contain !important; /* This preserves the aspect ratio */
}

current_task_preview_image_ui div.fixed img {
    max-width: 95vw !important;
    max-height: 50vh !important;
    object-fit: contain !important;
}

/* Makes the column a flex container that can stretch vertically */
.fill-height-column {
    height: 100%;
    display: flex;
    flex-direction: column;
}
/* --- NEW: Styling for progress bar and description to fill column width --- */
/* Target the HTML component for the progress bar */
#current_task_progress_bar_ui {
    width: 100% !important;
}

/* Makes the element containing the prompts grow to fill the available space */
#current_task_progress_description_ui {
    width: 100% !important;
}
/* Ensures the Textbox wrappers inside the container also grow */
.prompt-container { flex-grow: 1; display: flex; flex-direction: column; }
.prompt-container > .gr-form { flex-grow: 1; display: flex; flex-direction: column; }
.prompt-container > .gr-form > .gr-textarea-wrapper { flex-grow: 1; }
.total_segments_display > .gr-markdown { height: 100%; display: flex; flex-direction: column; justify-content: center; }
.current_task_progress_bar > .gr-html {}
"""

# Combine the main CSS with panel-specific CSS to create the final stylesheet.
APP_CSS = CSS_MAIN + CSS_TOP_PANEL + CSS_BOTTOM_PANEL