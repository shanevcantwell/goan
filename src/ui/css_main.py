# src/ui/css_main.py
# This file contains the main/global CSS for the Gradio application.
# It also imports and combines panel-specific CSS.

from .css_top_panel import TOP_PANEL_CSS

MAIN_CSS = """
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

/* --- Connected Button Group Styling --- */
/* Creates a visually connected group of buttons in a row. Applied via elem_classes="button-group". */
/* This new approach gives the container the border and removes it from the inner buttons,
   which prevents the "beveled" look from individual button borders. */
.button-group {
    gap: 0 !important;
    /* Add a border to the container itself and round its corners. */
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 0 !important; /* Squared off to match the top panel style */
    /* Hide overflow to ensure inner button corners are sharp and contained. */
    overflow: hidden;
}
/* Remove all borders and rounding from the buttons inside the group. */
.button-group > * .gr-button, .button-group > .gr-button {
    border: none !important;
    border-radius: 0 !important;
}
/* Add a separator line between buttons by adding a left border to all but the first. */
.button-group > *:not(:first-child), .button-group > .gr-button:not(:first-child) {
    border-left: 1px solid var(--border-color-primary) !important;
}

#queue_df { font-size: 0.9rem; }

/* --- Task Queue Column Styling --- */
/* Use a fixed table layout to enforce column widths accurately. */
#queue_df table {
    table-layout: fixed;
    width: 100%;
}

/* Default for all headers/cells: vertical alignment and basic padding. */
#queue_df th, #queue_df td {
    vertical-align: middle;
    padding: 4px;
}

/* --- NEW: Scrollable Prompt Cell --- */
/* This allows long prompts in the queue to be scrollable instead of taking up excess vertical space. */
.prompt-cell-scrollable {
    max-height: 6em; /* Sets a max height of about 4-5 lines of text */
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

/* Status Column (1): Fixed width, left-aligned, allows wrapping. */
#queue_df th:nth-child(6), #queue_df td:nth-child(6) {
    width: 8rem; /* Wide enough for "⏳ Processing" */
    text-align: left;
    white-space: normal; /* Allow text to wrap */
}

/* Prompt Column (7): Flexible width, left-aligned, truncates with ellipsis. */
#queue_df th:nth-child(2), #queue_df td:nth-child(2) {
    text-align: left;
    width: 40%; /* Adjust the width as needed */
    min-width: 10rem; /* Minimum width */
    white-space: normal; /* Allow text to wrap */
    word-break: break-word; /* Ensure long words break */
}

/* Image (8), Length (9), ID (10) Columns: Fixed width, centered. */
#queue_df th:nth-child(3), #queue_df td:nth-child(3) { width: 4rem; text-align: center; }
#queue_df th:nth-child(9), #queue_df td:nth-child(9) { width: 4rem; text-align: center; }
#queue_df th:nth-child(10), #queue_df td:nth-child(10) { width: 3rem; text-align: center; }

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

/* Custom blue color for specific action buttons */
#clear_image_button:not([disabled]), #download_image_button:not([disabled]) {
    background-color: #3b82f6 !important; /* A softer, less intense blue */
    color: white !important;
}
#clear_image_button:not([disabled]):hover, #download_image_button:not([disabled]):hover {
    background-color: #2563eb !important; /* A slightly darker blue for hover */
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

#current_task_preview_image_ui div.fixed img {
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
.total_segments_display > .gr-markdown { height: 100%; display: flex; flex-direction: column; justify-content: flex-end; }
.current_task_progress_bar > .gr-html {}
"""

# Combine the main CSS with panel-specific CSS to create the final stylesheet.
APP_CSS = MAIN_CSS + TOP_PANEL_CSS