# src/ui/css_bottom_panel.py
# This file contains the specific CSS for the main bottom panel container.

CSS_BOTTOM_PANEL = """
/* --- Bottom Section Container Styling --- */
/* This is the main wrapper for the bottom 2/3 of the UI */
.bottom-section-container {
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 0 !important; /* No rounding for the main container */
    box-shadow: none !important; /* No bevel */
    overflow: hidden; /* Crucial to hide any inner component rounding/shadows that might peek out */
    padding: 0 !important; /* Ensure no internal padding on the container itself */
    margin-top: var(--spacing-xxl) !important; /* Add space between top and bottom panels */
}

/* Reset styling for direct children (Rows, Columns, etc.) of the bottom section container */
.bottom-section-container > .gr-column,
.bottom-section-container > .gr-row,
.bottom-section-container > .gr-form,
.bottom-section-container > .gr-box,
.bottom-section-container > .gr-group {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important; /* Remove internal padding */
    margin: 0 !important; /* Remove internal margins */
}

/* Add a vertical separator between the two main columns in the settings section */
.bottom-section-container > .gr-row > .gr-column:not(:first-child) {
    border-left: 1px solid var(--border-color-primary) !important;
}

/* Reset padding/margin/borders for ALL Gradio components *within* the bottom section
   to ensure they are flush against each other and the container edges.
   This is an aggressive reset to ensure no default Gradio spacing interferes. */
.bottom-section-container .gr-form,
.bottom-section-container .gr-button,
.bottom-section-container .gr-file,
.bottom-section-container .gr-image,
.bottom-section-container .gr-box,
.bottom-section-container .gr-group,
.bottom-section-container .gr-row,
.bottom-section-container .gr-column,
.bottom-section-container .gr-data-frame {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Apply a top border to all direct children of the container (except the first one)
   to create horizontal separators between rows of components. */
.bottom-section-container > *:not(:first-child) {
    border-top: 1px solid var(--border-color-primary) !important;
}

/* Apply a top border to all direct children of columns within the container */
.bottom-section-container .gr-column > *:not(:first-child) {
    border-top: 1px solid var(--border-color-primary) !important;
}

/* Restore internal padding for specific interactive elements for better UX */
.bottom-section-container .gr-textarea-wrapper,
.bottom-section-container .gr-input,
.bottom-section-container .gr-slider-wrap,
.bottom-section-container .gr-file-input,
.bottom-section-container .gr-form label,
.bottom-section-container .gr-file label,
.bottom-section-container .gr-image label,
.bottom-section-container .gr-button,
.bottom-section-container .gr-radio {
    padding: var(--spacing-sm) !important;
}

/*
   FIX FOR SLIDER LABELS:
   The aggressive padding reset on .gr-form collapses the label area.
   This rule specifically targets the label wrapper inside a slider component
   and restores its visibility and spacing.
*/
.bottom-section-container .gradio-slider > .label-wrap {
    display: block !important;
    padding: var(--spacing-sm) var(--spacing-sm) 0 var(--spacing-sm) !important;
    margin-bottom: var(--spacing-xs) !important;
}


/* Ensure buttons inside the container don't have their own borders unless specified */
.bottom-section-container .gr-button {
    border: none !important;
    border-radius: 0 !important; /* Make buttons flush with edges */
}

/* Special handling for button groups to give them an outer border */
.bottom-section-container .button-group {
    border: 1px solid var(--border-color-primary) !important;
}
"""
