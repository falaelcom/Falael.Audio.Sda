CONFIG_RULES = {
    "": {  # Default styles for all charts
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
    
    ".exp01": {  # Experiment 01 specific styles
        "figure_width": 18,  # Wider for better correlation visibility
        "line_width": 1.2,   # Slightly thicker lines
        "grid_alpha": 0.4    # More visible grid
    },
    
    ".correlation": {  # Correlation analysis specific styles
        "figure_height": 12,     # Taller for multiple bands
        "line_alpha": 0.9,       # More opaque lines for clarity
        "reference_line_alpha": 0.7,  # More visible zero line
        "font_size_title": 16    # Larger title for importance
    },
    
    ".exp01.correlation": {  # Most specific: experiment 01 correlation charts
        "y_min_db": -80,     # Extended range for detailed analysis
        "y_max_db": 80,
        "line_width": 1.5,   # Thick lines for clarity
        "grid_alpha": 0.5,   # Strong grid for precise reading
        "dpi": 200           # High resolution for detailed analysis
    },
    
    ".dark.exp01.correlation": {  # Dark theme experiment 01 correlation
        "line_width": 1.8,   # Even thicker for dark background visibility
        "grid_alpha": 0.6,   # More visible grid on dark
        "reference_line_alpha": 0.8
    }
}