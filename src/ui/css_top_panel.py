# src/ui/css_top_panel.py
# This file contains the specific CSS for the main top panel container.

CSS_TOP_PANEL = """
/* --- Top Section Container Styling --- */
/* This is the main wrapper for the top 1/3 of the UI */
.top-section-container {
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 0 !important; /* No rounding for the main container */
    box-shadow: none !important; /* No bevel */
    overflow: hidden; /* Crucial to hide any inner component rounding/shadows that might peek out */
    padding: 0 !important; /* Ensure no internal padding on the container itself */
}

/* Reset styling for direct children (the columns) of the top section container */
.top-section-container > .gr-column {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important; /* Remove internal padding from columns */
    margin: 0 !important; /* Remove internal margins from columns */
    height: 100%; /* Make columns stretch vertically */
    display: flex;
    flex-direction: column; /* Arrange contents vertically */
}

/* Add a vertical separator between the two columns in the top section */
.top-section-container > .gr-column:not(:first-child) {
    border-left: 1px solid var(--border-color-primary) !important;
}

/* Reset padding/margin/borders for ALL Gradio components *within* the top section
   to ensure they are flush against each other and the column edges.
   This is an aggressive reset to ensure no default Gradio spacing interferes. */
.top-section-container .gr-form, /* For Textbox, Slider, Number */
.top-section-container .gr-button,
.top-section-container .gr-file,
.top-section-container .gr-image,
.top-section-container .gr-box,
.top-section-container .gr-group,
.top-section-container .gr-row,
.top-section-container .gr-column {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Now, apply the 1px border to the *internal* interactive elements/visual containers
   within each Gradio component, making them appear as individual bordered blocks.
   Also, add a top border to create horizontal separators between elements within columns. */

/* Apply top border to all components within columns (except the first one) */
.top-section-container .gr-column > *:not(:first-child) {
    border-top: 1px solid var(--border-color-primary) !important;
}

/* Textbox input area (for prompts and other text inputs) */
.top-section-container .gr-textarea-wrapper, /* For multiline prompts */
.top-section-container .gr-input { /* For single-line inputs like Seed, etc. */
    border: none !important; /* Border is applied by the parent column's top border */
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: var(--spacing-sm) !important; /* Restore some internal padding for text */
}

/* Slider track and number input */
.top-section-container .gr-slider-wrap {
    border: none !important; /* Border is applied by the parent column's top border */
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: var(--spacing-sm) !important; /* Adjust padding as needed */
}

/* File input area (the drop zone) */
.top-section-container .gr-file-input {
    border: none !important; /* Border is applied by the parent column's top border */
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: var(--spacing-sm) !important; /* Adjust padding as needed */
}

/* Image display area */
.top-section-container .gr-image-container {
    border: none !important; /* Border is applied by the parent column's top border */
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important; /* Image itself should fill, no padding */
}

/* Buttons: Re-apply border to buttons, allowing them to keep their default radius
   if they are not part of a button-group. The global .gr-button rule already does this. */
.top-section-container .gr-button {
    border: 1px solid var(--border-color-primary) !important;
    box-shadow: none !important;
    border-radius: var(--radius-lg) !important; /* Keep default button rounding */
    padding: var(--spacing-sm) !important; /* Restore button padding */
}

/* Specific overrides for the image file input (the green drop zone) */
#image_file_input_ui {
    border: none !important; /* Its border is now handled by the column's top border */
    border-radius: 0 !important;
    box-shadow: none !important;
    background-color: var(--color-accent-800); /* Keep its special background color */
}

/* Specific overrides for the input image display */
#input_image_display_ui {
    border: none !important; /* Its border is now handled by the column's top border */
    border-radius: 0 !important;
    box-shadow: none !important;
}

/* Ensure labels within components have proper padding */
.top-section-container .gr-form label,
.top-section-container .gr-file label,
.top-section-container .gr-image label {
    padding: var(--spacing-sm) !important;
    margin: 0 !important;
}
"""