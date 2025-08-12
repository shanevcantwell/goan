# src/ui/css_bottom_panel.py

CSS_BOTTOM_PANEL = """
/* --- Bottom Section Container Styling --- */
/* This is the main wrapper for the bottom 2/3 of the UI */
.bottom-section-container {
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 0 !important; /* No rounding for the main container */
    box-shadow: none !important; /* No bevel */
    overflow: hidden; /* Crucial to hide any inner component rounding/shadows that might peek out */
    padding: 0 !important; /* Ensure no internal padding on the container itself */
}

/* Reset styling for direct children (the columns) of the bottom section container */
.bottom-section-container > .gr-column {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important; /* Remove internal padding from columns */
    margin: 0 !important; /* Remove internal margins from columns */
    height: 100%; /* Make columns stretch vertically */
    display: flex;
    flex-direction: column; /* Arrange contents vertically */
}

/* Add a vertical separator between the two columns in the bottom section (if needed) */
.bottom-section-container > .gr-column:not(:first-child) {
    border-left: 1px solid var(--border-color-primary) !important;
}

/* Reset padding/margin/borders for ALL Gradio components *within* the bottom section
   to ensure they are flush against each other and the column edges.
   This is an aggressive reset to ensure no default Gradio spacing interferes. */
.bottom-section-container .gr-form, /* For Textbox, Slider, Number */
.bottom-section-container .gr-button,
.bottom-section-container .gr-file,
.bottom-section-container .gr-image,
.bottom-section-container .gr-box,
.bottom-section-container .gr-group,
.bottom-section-container .gr-row,
.bottom-section-container .gr-column {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Apply top border to all components within columns (except the first one) */
.bottom-section-container .gr-column > *:not(:first-child) {
    border-top: 1px solid var(--border-color-primary) !important;
}

/* Textbox input area styling */
.bottom-section-container .gr-textarea-wrapper, /* For multiline prompts */
.bottom-section-container .gr-input { /* For single-line inputs like Seed, etc. */
    border: none !important; /* Border is applied by the parent column's top border */
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Ensure labels within components have proper padding */
.bottom-section-container .gr-form label,
.bottom-section-container .gr-file label,
.bottom-section-container .gr-image label {
    padding: var(--spacing-sm) !important;
    margin: 0 !important;
}
"""

# --- Additional CSS for consistent spacing between UI elements ---
# This ensures the spacing is consistent with the top panel's design
CSS_BOTTOM_PANEL += """
/* Ensure consistent vertical spacing between components within columns */
.bottom-section-container .gr-column > * {
    /* Use flex-grow to fill available space if needed */
    flex: 0 0 auto; /* Don't grow, don't shrink, use natural size */
    /* Remove any default margins that might cause gaps */
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

/* Specific adjustments for the bottom panel's content area */
.bottom-section-container .gr-row {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    height: auto; /* Let it size based on content */
}

/* Ensure all buttons are flush with their container edges */
.bottom-section-container .gr-button {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: var(--spacing-sm) !important;
    margin: 0 !important;
}
"""
