import os
import matplotlib.pyplot as plt
import numpy as np
from .lib.config_jscss import init_config, get_config
from .image_fulltrack_lib.config import CONFIG_RULES

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    """
    Generate static charts from fulltrack time series data for visual correlation analysis.
    
    Creates multi-panel charts showing:
    - Energy changes over time per frequency band (from fulltrack data)
    - Fixed Y-axis (-60 to +60 dB) for consistent comparison
    - Time axis in seconds for easy interpretation
    """
    
    # Initialize configuration system
    init_config(config_dict=CONFIG_RULES)
    
    # Get resolved configuration for exp01.correlation chart
    resolved_config = get_config("exp01", "correlation")
    
    # Get fulltrack data - let KeyError bubble up if missing
    fulltrack_data = previous["freq_response_fulltrack"]["result"]
    
    # Configuration (use resolved config with fallbacks)
    y_min = resolved_config.get("y_min_db", -60)
    y_max = resolved_config.get("y_max_db", 60)
    figure_width = resolved_config.get("figure_width", 15)
    figure_height = resolved_config.get("figure_height", 10)
    line_width = resolved_config.get("line_width", 1.0)
    line_alpha = resolved_config.get("line_alpha", 0.8)
    grid_alpha = resolved_config.get("grid_alpha", 0.3)
    reference_line_alpha = resolved_config.get("reference_line_alpha", 0.5)
    reference_line_width = resolved_config.get("reference_line_width", 0.5)
    dpi = resolved_config.get("dpi", 150)
    font_size_title = resolved_config.get("font_size_title", 14)
    font_size_labels = resolved_config.get("font_size_labels", 10)
    
    # Theme colors
    background_color = resolved_config.get("background_color", "white")
    text_color = resolved_config.get("text_color", "black")
    grid_color = resolved_config.get("grid_color", "gray")
    reference_line_color = resolved_config.get("reference_line_color", "gray")
    line_colors = resolved_config.get("line_colors", ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"])
    
    # Get track filename for output naming
    track_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Extract data from all frequency bands
    bands_data = {}
    sample_rate = None
    
    for band_key, band_info in fulltrack_data.items():
        # Let KeyError bubble up if structure is wrong
        data = band_info["track_relative_energy_db"]
        
        # Get sample rate (same for all bands)
        if sample_rate is None:
            sample_rate = data["sample_rate"]
        
        # Reconstruct actual dB values
        origin_value = data["origin_value"]
        origin_sample = data["origin_sample"] 
        interval_samples = data["interval_samples"]
        relative_values = data["values"]
        
        # Convert to actual dB values
        actual_db_values = [origin_value + rv for rv in relative_values]
        
        # Convert sample positions to time in seconds
        time_points = []
        for i in range(len(relative_values)):
            sample_position = origin_sample + (i * interval_samples)
            time_seconds = sample_position / sample_rate
            time_points.append(time_seconds)
        
        bands_data[band_key] = {
            "time_seconds": time_points,
            "db_values": actual_db_values
        }
    
    # Let any exception bubble up if no bands_data - indicates real problem
    assert bands_data, "No frequency bands found in fulltrack data"
    
    # Define num_bands based on the number of frequency bands
    num_bands = len(bands_data)
    
    # Create multi-panel plot with theme styling
    plt.style.use('default')  # Reset any previous styles
    fig, axes = plt.subplots(num_bands, 1, figsize=(figure_width, figure_height), 
                            sharex=True, sharey=True, facecolor=background_color)
    
    # Handle single band case
    if num_bands == 1:
        axes = [axes]
    
    # Plot each frequency band
    for idx, (band_key, data) in enumerate(bands_data.items()):
        ax = axes[idx]
        
        # Set subplot background color
        ax.set_facecolor(background_color)
        
        # Get line color (cycle through available colors)
        line_color = line_colors[idx % len(line_colors)]
        
        # Plot the line with styled properties
        ax.plot(data["time_seconds"], data["db_values"], 
               linewidth=line_width, alpha=line_alpha, color=line_color)
        
        # Set fixed Y-axis range
        ax.set_ylim(y_min, y_max)
        
        # Add styled horizontal line at 0 dB (track average)
        ax.axhline(y=0, color=reference_line_color, linestyle='--', 
                  alpha=reference_line_alpha, linewidth=reference_line_width)
        
        # Styling with configured properties and theme colors
        ax.set_ylabel(f"{band_key}\n(dB)", fontsize=font_size_labels, color=text_color)
        ax.grid(True, alpha=grid_alpha, color=grid_color)
        ax.set_title(f"Track-Relative Energy: {band_key}", fontsize=font_size_labels, color=text_color)
        
        # Set tick colors
        ax.tick_params(colors=text_color, which='both')
        
        # Set spine colors
        for spine in ax.spines.values():
            spine.set_color(text_color)
    
    # Set X-axis label only on bottom plot
    axes[-1].set_xlabel("Time (seconds)", fontsize=font_size_labels, color=text_color)
    
    # Overall title with configured font size and theme color
    fig.suptitle(f"Frequency Band Energy Analysis: {track_name}", 
                fontsize=font_size_title, color=text_color)
    
    # Tight layout for better spacing
    plt.tight_layout()
    
    # Save the plot to fulltrack subdirectory with new naming convention
    fulltrack_dir = os.path.join(out_path, "fulltrack")
    os.makedirs(fulltrack_dir, exist_ok=True)
    
    output_filename = f"exp01.correlation.{track_name}.png"
    output_path = os.path.join(fulltrack_dir, output_filename)
    
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', 
               facecolor=background_color, edgecolor='none')
    plt.close()  # Free memory
    
    # Calculate max time across all bands
    max_time = 0
    for data in bands_data.values():
        if data["time_seconds"]:
            max_time = max(max_time, max(data["time_seconds"]))
    
    result = {
        "output_file": output_path,
        "bands_plotted": list(bands_data.keys()),
        "time_range_seconds": [0, max_time],
        "y_axis_range_db": [y_min, y_max]
    }
    
    return {"result": result}