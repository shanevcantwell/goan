# src/ui/css_main.py
# This file contains the main/global CSS for the Gradio application.
# It also imports and combines panel-specific CSS.

from .css_top_panel import CSS_TOP_PANEL
from .css_bottom_panel import CSS_BOTTOM_PANEL

CSS_MAIN = """
/* --- New Color Palette & Gradio Theme Overrides --- */
:root {
    /* Core Palette inspired by FramePack & User Feedback */
    --color-bg: #111111;
    --color-panel: #1A1D22;
    --color-text-main: #E0E0E0;
    --color-text-dim: #999999;
    --color-border: #2A2A2A;
    --color-accent-slider: #D4A26A; /* Amber for sliders and highlights */
    --color-positive: #16a34a; /* Green for primary/confirm actions */
    --color-positive-hover: #15803d;
    --color-destructive: #dc2626;
    --color-destructive-hover: #b91c1c;
    --color-button-neutral: #374151;
    --color-button-neutral-hover: #4b5563;

    /* Gradio Theme Variable Overrides */
    --body-background-fill: var(--color-bg) !important;
    --background-fill-primary: var(--color-panel) !important;
    --background-fill-secondary: var(--color-bg) !important;
    --border-color-primary: var(--color-border) !important;
    --embed-radius: 0 !important;
    --shadow-drop: none !important;
    --shadow-drop-lg: none !important;
    --body-text-color: var(--color-text-main) !important;
    --body-text-color-subdued: var(--color-text-dim) !important;
    --slider-color: var(--color-accent-slider) !important;
    --checkbox-label-background-fill-hover: #333 !important;
    --checkbox-label-background-fill-selected: var(--color-panel) !important;
    --checkbox-label-border-color-selected: var(--color-accent-slider) !important;
    --checkbox-border-color-selected: var(--color-accent-slider) !important;
    --checkbox-background-selected: var(--color-accent-slider) !important;
}

body {
    background-color: var(--body-background-fill);
    color: var(--body-text-color);
}

.gradio-container {
    background-color: transparent !important;
    max-width: 95% !important;
    margin: auto !important;
}

/* --- Global Layout & Style Adjustments --- */
.gradio-container .gr-row, .gradio-container .gr-column, .gradio-container .gr-form {
    gap: 0 !important;
}

/* --- Utility Class for Flat Inputs --- */
.flat-input {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.flat-input textarea {
    background-color: transparent !important;
}
.flat-input > div[data-testid="image"] {
    border: none !important;
}

/* --- Standardized Button Styles (Targeting Gradio Variants) --- */
.gradio-container .gr-button {
    box-shadow: none !important;
    font-weight: 600 !important;
    border: none !important;
}

/* Default/Neutral Button Style (variant="secondary") */
.gradio-container .gr-button.gr-button-secondary {
    background: var(--color-button-neutral) !important;
    color: var(--color-text-main) !important;
}
.gradio-container .gr-button.gr-button-secondary:hover {
    background: var(--color-button-neutral-hover) !important;
}

/* Primary/Positive Button Style (variant="primary") */
.gradio-container .gr-button.gr-button-primary {
    background: var(--color-positive) !important;
    color: white !important;
}
.gradio-container .gr-button.gr-button-primary:hover {
    background: var(--color-positive-hover) !important;
}

/* Destructive Button Style (variant="stop") */
.gradio-container .gr-button.gr-button-stop {
    background: var(--color-destructive) !important;
    color: white !important;
}
.gradio-container .gr-button.gr-button-stop:hover {
    background: var(--color-destructive-hover) !important;
}

.gradio-container .gr-button[disabled] {
    background: #282c34 !important;
    color: #6a737d !important;
    border-color: var(--border-color-primary) !important;
    opacity: 0.7;
}


/* --- Task Queue Table Styling --- */
#queue_df { font-size: 0.9rem; }
#queue_df table {
    width: 100%;
    border-collapse: collapse;
}
#queue_df th, #queue_df td {
    vertical-align: middle;
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid var(--border-color-primary);
}
#queue_df th {
    font-weight: bold;
    background-color: #25282e;
    border-bottom: 1px solid var(--color-accent-slider) !important;
}
.prompt-cell-scrollable {
    max-height: 5em;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
    text-align: left;
    padding-right: 5px;
}
#queue_df th:nth-child(1), #queue_df td:nth-child(1) { min-width: 10rem; text-align: left; white-space: normal; }
#queue_df th:nth-child(2), #queue_df td:nth-child(2) { text-align: left; width: 100%; }
#queue_df th:nth-child(3), #queue_df td:nth-child(3),
#queue_df th:nth-child(4), #queue_df td:nth-child(4),
#queue_df th:nth-child(5), #queue_df td:nth-child(5) { width: auto; text-align: center; }


/* --- Component-Specific Fixes & Minor Styles --- */
.compact-row > * { padding-top: 0 !important; padding-bottom: 0 !important; margin-top: 0 !important; margin-bottom: 0 !important; }
.compact-row .gr-html { min-height: unset !important; line-height: 1.2em !important; }
.compact-row .gradio-slider { padding-top: 0 !important; padding-bottom: 0 !important; }
.compact-group, .compact-group > * { padding: 0 !important; margin: 0 !important; }
.button-group { gap: 0 !important; border: 1px solid var(--border-color-primary) !important; border-radius: 0 !important; overflow: hidden; }
#settings_menu_checkbox_group span[data-testid="block-info"] { display: none !important; }
fieldset#settings_menu_checkbox_group.button-group { border: none !important; }
div.fixed img { width: auto !important; height: auto !important; max-width: 95vw !important; max-height: 95vh !important; object-fit: contain !important; }
current_task_preview_image_ui div.fixed img { max-width: 95vw !important; max-height: 50vh !important; object-fit: contain !important; }
#current_task_progress_bar_ui, #current_task_progress_description_ui { width: 100% !important; }
"""

# Combine the main CSS with panel-specific CSS to create the final stylesheet.
APP_CSS = CSS_MAIN + CSS_TOP_PANEL + CSS_BOTTOM_PANEL
