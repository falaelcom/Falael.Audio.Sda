# Image fingerprint configuration using CSS-like JSON approach

# Default configuration - all values go in the root "" selector
CONFIG_RULES = {
    "": {
        # Datapoint dimensions
        "DATAPOINT_WIDTH_PX": 45,   # Pixel width of each data point
        "DATAPOINT_HEIGHT_PX": 45,  # Pixel height of each data point

        # Vertical layout (relative to DATAPOINT_HEIGHT_PX)
        "page_top_padding": 1.5,      # Top margin of the page
        "label_strip_height": 1,    # Height for column labels
        "minor_label_strip_height": 1.4,    # Height for intracell column labels
        "data_grid_top_margin": 0.6,  # Space above data grid
        "data_grid_bottom_margin": 1, # Space below data grid
        "page_bottom_padding": 2,   # Bottom margin of the page
        
        # Horizontal layout (relative to DATAPOINT_WIDTH_PX)
        "page_left_padding": 1.5,      # Left margin of the page
        "vertical_label_strip_width": 3.5, # Width for row labels
        "vertical_minor_label_strip_width": 2, # Width for intracell row labels
        "data_grid_left_margin": 0.6, # Space left of data grid
        "data_grid_right_margin": 1, # Space right of data grid
        "page_right_padding": 1.5,     # Right margin of the page
        
        # Grid wrapping configuration
        "max_hgrid_cells_per_line": 3,     # Max horizontal grid cells before wrapping to next line (ZICV)
        "max_vgrid_cells_per_column": 2,   # Max vertical grid cells before wrapping to next column (ZICH)
        
        # Grid spacing (in absolute pixels)
        "gridHSpacingPx": 1,        # Horizontal spacing between grid cells
        "gridVSpacingPx": 1,        # Vertical spacing between grid cells
        "gridLinesColor": "#999999", # Color of grid lines
        "minorGridLinesColor": "#222222", # Color of minor grid lines (intracell)
        
        # Metric color indicators
        "metric_color_indicator_size": 0.3,  # Size of min/max color bars relative to arrangement direction

        # Font configuration - relative to datapoint dimensions
        "horizontal_label_font_name": "./fonts/OpenSans-CondBold.ttf",
        "horizontal_label_font_ratio": 0.4,  # Relative to datapoint_width for major horizontal labels
        "horizontal_label_45deg_font_ratio": 0.25,  # Relative to datapoint diagonal for 45° rotated labels
        "horizontal_label_fg_color": "#FFFFFF",
        "horizontal_label_bg_color": "#111111",
        
        "vertical_label_font_name": "./fonts/OpenSans-CondBold.ttf", 
        "vertical_label_font_ratio": 0.35,  # Relative to datapoint_height for vertical labels
        "vertical_label_fg_color": "#FFFFFF",
        "vertical_label_bg_color": "#111111",
        
        # Title configuration (for Z-file mode)
        "title_font_name": "./fonts/OpenSans-CondBold.ttf",
        "title_font_ratio": 0.6,  # Relative to datapoint_height
        "title_fg_color": "#FFFFFF",
        "title_top_margin": 0.2,   # Space above title (relative to datapoint_height)
        "title_bottom_margin": 0.4, # Space below title (relative to datapoint_height)
    },

    "bmt": {
        "max_hgrid_cells_per_line": 5,     # Max horizontal grid cells before wrapping to next line (ZICV)
        "max_vgrid_cells_per_column": 4,   # Max vertical grid cells before wrapping to next column (ZICH)
    },
    
    "tmb": {
        "max_hgrid_cells_per_line": 6,     # Max horizontal grid cells before wrapping to next line (ZICV)
        "max_vgrid_cells_per_column": 5,   # Max vertical grid cells before wrapping to next column (ZICH)
    },

    "mbt": {
        "max_hgrid_cells_per_line": 8,     # Max horizontal grid cells before wrapping to next line (ZICV)
        "max_vgrid_cells_per_column": 5,   # Max vertical grid cells before wrapping to next column (ZICH)
    },

    "mtb": {
        "max_hgrid_cells_per_line": 5,     # Max horizontal grid cells before wrapping to next line (ZICV)
        "max_vgrid_cells_per_column": 3,   # Max vertical grid cells before wrapping to next column (ZICH)
    },

    # Additional rules can be added here later, e.g.:
    # ".tbm": {
    #     "DATAPOINT_WIDTH_PX": 35,
    #     "page_top_padding": 1.5
    # },
    # ".zf": {
    #     "vertical_label_strip_width": 4.0
    # }
}