ALGO_VERSION = "v003" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_metrics.base_freq_response_fulltrack as base_freq_response_fulltrack

import os
import matplotlib.pyplot as plt



from zulu.fs_cache_utils import get_file_timestamps, get_keys, sanitate_params

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:
    """
    Generate static charts from fulltrack time series data for visual correlation analysis.
    
    Creates multi-panel charts showing:
    - Energy changes over time per frequency band (from fulltrack data)
    - Fixed Y-axis (-60 to +60 dB) for consistent comparison
    - Time axis in seconds for easy interpretation
    """

    assert (freq_response_fulltrack_data := session_data[base_freq_response_fulltrack.PROCESSOR_NAME]["result"])
    assert (freq_response_fulltrack_params := session_data[base_freq_response_fulltrack.PROCESSOR_NAME]["params"])

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    configJSCSS_styles = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.STYLES_FULLTRACK", selector = "base_freq_response_fulltrack")
    styles = configJSCSS_styles.to_graph()

    # Layout styles
    y_min = styles.get("y_min_db", -60)
    y_max = styles.get("y_max_db", 60)
    figure_width = styles.get("figure_width", 15)
    figure_height = styles.get("figure_height", 10)
    line_width = styles.get("line_width", 1.0)
    line_alpha = styles.get("line_alpha", 0.8)
    grid_alpha = styles.get("grid_alpha", 0.3)
    reference_line_alpha = styles.get("reference_line_alpha", 0.5)
    reference_line_width = styles.get("reference_line_width", 0.5)
    dpi = styles.get("dpi", 150)
    font_size_title = styles.get("font_size_title", 14)
    font_size_labels = styles.get("font_size_labels", 10)
    
    # Theme color styles
    background_color = styles.get("background_color", "white")
    text_color = styles.get("text_color", "black")
    grid_color = styles.get("grid_color", "gray")
    reference_line_color = styles.get("reference_line_color", "gray")
    line_colors = styles.get("line_colors", ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"])

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        base_freq_response_fulltrack.PROCESSOR_NAME: freq_response_fulltrack_params,

        "_c_y_min": y_min,
        "_c_y_max": y_max,
        "_c_figure_width": figure_width,
        "_c_figure_height": figure_height,
        "_c_line_width": line_width,
        "_c_line_alpha": line_alpha,
        "_c_grid_alpha": grid_alpha,
        "_c_reference_line_alpha": reference_line_alpha,
        "_c_reference_line_width": reference_line_width,
        "_c_dpi": dpi,
        "_c_font_size_title": font_size_title,
        "_c_font_size_labels": font_size_labels,

        "_c_background_color": background_color,
        "_c_text_color": text_color,
        "_c_grid_color": grid_color,
        "_c_reference_line_color": reference_line_color,
        "_c_line_colors": line_colors,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))
    out_root = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)
    os.makedirs(out_root, exist_ok=True)

    # Get track filename for output naming
    track_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Extract data from all frequency bands
    bands_data = {}
    sample_rate = None
    
    for band_key, band_info in freq_response_fulltrack_data.items():
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
    output_filename = f"{base_freq_response_fulltrack.PROCESSOR_NAME}.{track_name}.png"
    output_path = os.path.join(out_root, output_filename)
    
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', 
               facecolor=background_color, edgecolor='none')
    plt.close()  # Free memory
    
    # Calculate max time across all bands
    max_time = 0
    for data in bands_data.values():
        if data["time_seconds"]:
            max_time = max(max_time, max(data["time_seconds"]))
    
    data = {
        "params_version": new_params_version, 
        "params": params,
        "result": {
            "dir_name": out_root,
            "file_name": output_filename,
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }