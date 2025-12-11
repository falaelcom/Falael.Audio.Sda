CONFIG = {
    "image_fulltrack.STYLES_FULLTRACK": {
        "*": {  # Default styles for all charts
            "y_min_db": -60,
            "y_max_db": 60,
            "figure_width": 15,
            "figure_height": 10,
            "line_width": 1.0,
            "line_alpha": 0.8,
            "grid_alpha": 0.3,
            "reference_line_alpha": 0.5,
            "reference_line_width": 0.5,
            "dpi": 150,
            "font_size_title": 14,
            "font_size_labels": 10,
            "tight_layout": True,
            "background_color": "black",
            "text_color": "white",
            "grid_color": "#666666",
            "reference_line_color": "#888888",
            "grid_alpha": 0.4,
            "reference_line_alpha": 0.6,
            # Lighter, more vibrant colors for dark background
            "line_colors": ["#4CAF50", "#FF9800", "#2196F3", "#F44336", "#9C27B0",
                           "#FF5722", "#E91E63", "#CDDC39", "#00BCD4", "#FFC107"]
        },
    
        "base_freq_response_fulltrack": {
            "figure_width": 18,
            "line_width": 1.2,
            "grid_alpha": 0.4,

            "figure_height": 12,
            "line_alpha": 0.9,
            "reference_line_alpha": 0.8,
            "font_size_title": 16,

            "y_min_db": -80,
            "y_max_db": 80,
            "line_width": 1.8,
            "grid_alpha": 0.6,
            "dpi": 200
        },
    },
}