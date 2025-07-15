import os
import numpy as np
import colorsys
import spectra
from .image_fingerprint_lib.data_regrouping import get_data_view, query_keys
from .image_fingerprint_lib.drawing_surface import DrawingSurface
from .image_fingerprint_lib.config_jscss import init_config, get_config
from .image_fingerprint_lib.config import CONFIG_RULES
from .image_fingerprint_lib.metrics import METRICS

def get_color(metric_index, normalized_value, bipolar, num_metrics):
    """Generate color for metrics using LCH color space for proper vividness control"""
    # Use second half spectrum (180-360 degrees) for primary colors
    primary_hue = 180 + (metric_index / num_metrics) * 180
    
    if bipolar:
        # -1 to 1 range with variable lightness and max chroma
        complementary_hue = (primary_hue + 180) % 360
        
        # Convert [-1, 1] to blend ratios
        primary_ratio = (normalized_value + 1) / 2  # Maps [-1,1] to [0,1]
        complementary_ratio = 1 - primary_ratio
        
        # Variable lightness: 50% at extremes (±1), 25% at center (0)
        abs_value = abs(normalized_value)
        lightness = 25 + (abs_value * 25)  # Maps [0,1] to [25%, 50%]
        chroma = 100  # Maximum vividness for all values
        
        # Create colors in LCH space and blend in RGB
        primary_color = spectra.lch(lightness, chroma, primary_hue)
        complementary_color = spectra.lch(lightness, chroma, complementary_hue)
        
        # Blend RGB values
        primary_rgb = primary_color.clamped_rgb
        complementary_rgb = complementary_color.clamped_rgb
        
        r = primary_rgb[0] * primary_ratio + complementary_rgb[0] * complementary_ratio
        g = primary_rgb[1] * primary_ratio + complementary_rgb[1] * complementary_ratio
        b = primary_rgb[2] * primary_ratio + complementary_rgb[2] * complementary_ratio
        
        return (int(r*255), int(g*255), int(b*255))
    else:
        # 0 to 1 range: variable lightness with max chroma at value=1
        hue = primary_hue
        lightness = 25 + (normalized_value * 25)  # Maps [0,1] to [25%, 50%] - same range as bipolar
        chroma = normalized_value * 100  # Maps [0,1] to [0, 100] chroma - maximum vividness at 1
        
        # Create color in LCH space
        color = spectra.lch(lightness, chroma, hue)
        rgb = color.clamped_rgb  # Use clamped RGB to stay in gamut
        
        return (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))

def permutation_string_to_list(perm_str):
    """Convert permutation string like 'btm' to list like ['B', 'T', 'M']"""
    char_map = {'b': 'B', 't': 'T', 'm': 'M'}
    return [char_map[char.lower()] for char in perm_str]

def sanitize_filename(filename):
    """Replace invalid filename characters with safe alternatives"""
    # Replace colons with hyphens and other problematic characters
    replacements = {
        ':': '.',
        '<': '_',
        '>': '_',
        '"': "'",
        '|': '_',
        '?': '_',
        '*': '_',
        '/': '_',
        '\\': '_'
    }
    
    for char, replacement in replacements.items():
        filename = filename.replace(char, replacement)
    
    return filename

def process_permutation(file_path: str, out_path: str, config: dict, previous: dict, perm_str: str) -> dict:
    """Process a single permutation and generate fingerprint images"""
    result = {}
    
    # Convert permutation string to list
    permutation = permutation_string_to_list(perm_str)
    
    # Get data view for this permutation
    data_view, sorted_keys = get_data_view(previous, permutation, METRICS, config)
    
    # Get labels using sorted keys
    band_labels = query_keys(sorted_keys, permutation, 'B')
    time_labels = query_keys(sorted_keys, permutation, 'T')
    metric_labels = [METRICS[key]["title"] for key in METRICS.keys()]
    
    # Calculate dimensions
    num_bands = len(band_labels)
    num_times = len(time_labels)
    num_metrics = len(METRICS)
    
    # Get dynamic dimensions based on permutation
    x_labels = metric_labels if permutation[0] == 'M' else query_keys(sorted_keys, permutation, permutation[0])
    y_labels = metric_labels if permutation[1] == 'M' else query_keys(sorted_keys, permutation, permutation[1])
    z_labels = metric_labels if permutation[2] == 'M' else query_keys(sorted_keys, permutation, permutation[2])
    num_x = len(x_labels)
    num_y = len(y_labels)
    num_z = len(z_labels)
    
    # Get filename for output naming
    full_filename = os.path.basename(file_path)
    
    def render_layout(layout_name, z_mode, intracell_cols, intracell_rows):
        """Helper function to render a specific layout"""
        # Get resolved configuration for current layout
        resolved_config = get_config(layout_name, z_mode)
        
        # Create drawing surface
        surface = DrawingSurface(
            grid_cols=num_x,
            grid_rows=num_y,
            intracell_cols=intracell_cols,
            intracell_rows=intracell_rows,
            legend_rows=0,
            legend_cols=0,
            config=resolved_config
        )
        
        # Get wrapping configuration
        if z_mode == "zicv":
            max_cells_per_page = resolved_config["max_hgrid_cells_per_line"]
        else:  # zich
            max_cells_per_page = resolved_config["max_vgrid_cells_per_column"]
        
        # Get sorted keys for iteration
        sorted_z_keys = query_keys(sorted_keys, permutation, permutation[2])
        sorted_y_keys = query_keys(sorted_keys, permutation, permutation[1])
        sorted_x_keys = query_keys(sorted_keys, permutation, permutation[0])
        
        # Draw data points - navigate through z→y→x tree using sorted keys
        for z_idx, z_key in enumerate(sorted_z_keys):  # z-level - USE SORTED KEYS
            for y_idx, y_key in enumerate(sorted_y_keys):  # y-level - USE SORTED KEYS
                for x_idx, x_key in enumerate(sorted_x_keys):  # x-level - USE SORTED KEYS
                    # Check if this combination exists in the data
                    if (z_key in data_view and 
                        y_key in data_view[z_key] and 
                        x_key in data_view[z_key][y_key]):
                        
                        data_point = data_view[z_key][y_key][x_key]
                        
                        # FIXED: Always determine which metric this data point represents
                        metric_key = None
                        if permutation[0] == 'M':
                            metric_key = x_key
                        elif permutation[1] == 'M':
                            metric_key = y_key
                        elif permutation[2] == 'M':
                            metric_key = z_key
                        
                        # FIXED: Always use metric index for coloring
                        if metric_key:
                            original_metric_idx = list(METRICS.keys()).index(metric_key)
                            color = get_color(original_metric_idx, data_point['value'], data_point['bipolar'], num_metrics)
                        else:
                            # Fallback (shouldn't happen if metrics are in one of the dimensions)
                            color = (128, 128, 128)  # Gray fallback
                        
                        # Calculate page and local coordinates
                        if z_mode == "zicv":
                            # ZICV: wrap horizontally (x direction)
                            page_number = x_idx // max_cells_per_page
                            page_x_idx = x_idx % max_cells_per_page
                            surface.draw_datapoint(page_number, page_x_idx, y_idx, z_idx, 0, color)
                        else:  # zich
                            # ZICH: wrap vertically (y direction)
                            page_number = y_idx // max_cells_per_page
                            page_y_idx = y_idx % max_cells_per_page
                            surface.draw_datapoint(page_number, x_idx, page_y_idx, 0, z_idx, color)
        
        # FIXED: Prepare color indicators based on which axis has metrics
        indicators_info = []
        
        if permutation[0] == 'M':
            # X-dimension is metrics - indicators span full grid cells horizontally
            for metric_idx, metric_key in enumerate(METRICS.keys()):
                metric_config = METRICS[metric_key]
                
                # Determine min/max values based on metric type
                if metric_config["type"] == "bipolar":
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["type"] == "bipolar", num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["type"] == "bipolar", num_metrics)
                
                indicators_info.append({
                    'metric_index': metric_idx,
                    'min_color': min_color,
                    'max_color': max_color,
                    'grid_position': metric_idx
                })
            
            # Draw color indicators for all pages - x-axis mode
            axis_type = "x-axis"
            
        elif permutation[1] == 'M':
            # Y-dimension is metrics - indicators span full grid cells vertically
            for metric_idx, metric_key in enumerate(METRICS.keys()):
                metric_config = METRICS[metric_key]
                
                # Determine min/max values based on metric type
                if metric_config["type"] == "bipolar":
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["type"] == "bipolar", num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["type"] == "bipolar", num_metrics)
                
                indicators_info.append({
                    'metric_index': metric_idx,
                    'min_color': min_color,
                    'max_color': max_color,
                    'grid_position': metric_idx
                })
            
            # Draw color indicators for all pages - y-axis mode
            axis_type = "y-axis"
            
        else:  # permutation[2] == 'M'
            # Z-dimension is metrics - indicators as intracell
            for metric_idx, metric_key in enumerate(METRICS.keys()):
                metric_config = METRICS[metric_key]
                
                # Determine min/max values based on metric type
                if metric_config["type"] == "bipolar":
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["type"] == "bipolar", num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["type"] == "bipolar", num_metrics)
                
                indicators_info.append({
                    'metric_index': metric_idx,
                    'min_color': min_color,
                    'max_color': max_color,
                    'grid_position': metric_idx
                })
            
            # Draw color indicators for all pages - z-intracell mode
            axis_type = "z-intracell"
        
        # Draw color indicators for all pages
        for page_number in range(surface.total_pages):
            # Calculate grid dimensions for this page
            if surface.layout_mode == "zicv":
                page_grid_cols = surface.cells_per_page
                page_grid_rows = surface.orthogonal_cells
                max_cells_per_page = surface.config["max_hgrid_cells_per_line"]
            else:  # zich
                page_grid_cols = surface.orthogonal_cells
                page_grid_rows = surface.cells_per_page
                max_cells_per_page = surface.config["max_vgrid_cells_per_column"]
    
            if axis_type == "z-file":
                # Full-width horizontal bars above and below entire grid
                if indicators_info:
                    metric = indicators_info[0]  # Single metric in file mode
                    surface.draw_horizontal_indicators_full_grid(page_number, metric['min_color'], metric['max_color'])
    
            elif axis_type == "z-intracell":
                # Z-intracell: all metrics on every page
                if z_mode == "zicv":  # Vertical intracell (metrics as columns)
                    for metric in indicators_info:
                        intracell_col = metric['metric_index']
                        for row in range(page_grid_rows):
                            for col in range(page_grid_cols):
                                surface.draw_horizontal_indicators_intracell_column(
                                    page_number, row, col, intracell_col, 
                                    metric['min_color'], metric['max_color']
                                )
                else:  # zich - Horizontal intracell (metrics as rows)
                    for metric in indicators_info:
                        intracell_row = metric['metric_index']
                        for row in range(page_grid_rows):
                            for col in range(page_grid_cols):
                                surface.draw_vertical_indicators_intracell_row(
                                    page_number, row, col, intracell_row,
                                    metric['min_color'], metric['max_color']
                                )
    
            elif axis_type == "x-axis":
                # X-axis metrics: only draw metrics visible on this page (ZICV paging)
                if surface.layout_mode == "zicv":
                    start_x = page_number * max_cells_per_page
                    end_x = min(start_x + max_cells_per_page, len(indicators_info))
            
                    for global_metric_idx in range(start_x, end_x):
                        if global_metric_idx < len(indicators_info):
                            metric = indicators_info[global_metric_idx]
                            local_col = global_metric_idx - start_x
                            surface.draw_horizontal_indicators_grid_cell(
                                page_number, local_col, 
                                metric['min_color'], metric['max_color']
                            )
                else:  # zich - all x-metrics on every page
                    for metric in indicators_info:
                        grid_col = metric['grid_position']
                        surface.draw_horizontal_indicators_grid_cell(
                            page_number, grid_col, 
                            metric['min_color'], metric['max_color']
                        )
    
            elif axis_type == "y-axis":
                # Y-axis metrics: only draw metrics visible on this page (ZICH paging)
                if surface.layout_mode == "zich":
                    start_y = page_number * max_cells_per_page
                    end_y = min(start_y + max_cells_per_page, len(indicators_info))
            
                    for global_metric_idx in range(start_y, end_y):
                        if global_metric_idx < len(indicators_info):
                            metric = indicators_info[global_metric_idx]
                            local_row = global_metric_idx - start_y
                            surface.draw_vertical_indicators_grid_cell(
                                page_number, local_row,
                                metric['min_color'], metric['max_color']
                            )
                else:  # zicv - all y-metrics on every page
                    for metric in indicators_info:
                        grid_row = metric['grid_position']
                        surface.draw_vertical_indicators_grid_cell(
                            page_number, grid_row,
                            metric['min_color'], metric['max_color']
                        )
        
        # Draw grid lines for all pages
        for page_number in range(surface.total_pages):
            surface.draw_grid_lines(page_number)
        
        # Draw labels for all pages
        if z_mode == "zicv":
            # ZICV: horizontal labels wrap with pages
            for page_number in range(surface.total_pages):
                start_x = page_number * max_cells_per_page
                end_x = min(start_x + max_cells_per_page, len(x_labels))
                
                # Draw horizontal label strip (right-to-left to avoid overlap)
                for global_x_idx in range(end_x - 1, start_x - 1, -1):
                    local_x_idx = global_x_idx - start_x
                    surface.draw_hlabel_strip(page_number, local_x_idx, x_labels[global_x_idx])
                
                # Draw minor horizontal label strip if needed
                if surface.intracell_cols > 1:
                    for global_x_idx in range(end_x - 1, start_x - 1, -1):
                        local_x_idx = global_x_idx - start_x
                        for intracell_col in range(len(z_labels) - 1, -1, -1):
                            surface.draw_intracell_hlabel_strip(page_number, local_x_idx, intracell_col, z_labels[intracell_col])
                
                # Draw vertical labels (same for all pages in ZICV)
                for y_idx in range(len(y_labels)):
                    surface.draw_vlabel_strip(page_number, y_idx, y_labels[y_idx])
                
                # Draw minor vertical labels if needed
                if surface.intracell_rows > 1:
                    for y_idx in range(len(y_labels)):
                        for intracell_row in range(len(z_labels)):
                            surface.draw_intracell_vlabel_strip(page_number, y_idx, intracell_row, z_labels[intracell_row])
        
        else:  # zich
            # ZICH: vertical labels wrap with pages
            for page_number in range(surface.total_pages):
                start_y = page_number * max_cells_per_page
                end_y = min(start_y + max_cells_per_page, len(y_labels))
                
                # Draw horizontal labels (same for all pages in ZICH)
                for x_idx in range(len(x_labels) - 1, -1, -1):
                    surface.draw_hlabel_strip(page_number, x_idx, x_labels[x_idx])
                
                # Draw minor horizontal labels if needed
                if surface.intracell_cols > 1:
                    for x_idx in range(len(x_labels) - 1, -1, -1):
                        for intracell_col in range(len(z_labels) - 1, -1, -1):
                            surface.draw_intracell_hlabel_strip(page_number, x_idx, intracell_col, z_labels[intracell_col])
                
                # Draw vertical label strip
                for global_y_idx in range(start_y, end_y):
                    local_y_idx = global_y_idx - start_y
                    surface.draw_vlabel_strip(page_number, local_y_idx, y_labels[global_y_idx])
                
                # Draw minor vertical labels if needed
                if surface.intracell_rows > 1:
                    for global_y_idx in range(start_y, end_y):
                        local_y_idx = global_y_idx - start_y
                        for intracell_row in range(len(z_labels)):
                            surface.draw_intracell_vlabel_strip(page_number, local_y_idx, intracell_row, z_labels[intracell_row])        
        
        # Save image in fingerprint subdirectory
        output_filename = f"{perm_str}.{z_mode}.{full_filename}.png"
        output_path = os.path.join(out_path, "fingerprint", output_filename)
        surface.save(output_path)
        
        return output_path
    
    # Render all layouts for this permutation
    perm_output_paths = []
    # 1. Z-Intracell-Vertical (z-dimension as columns)
    output_path_zicv = render_layout(perm_str, "zicv", num_z, 1)
    perm_output_paths.append(output_path_zicv)
    
    # 2. Z-Intracell-Horizontal (z-dimension as rows)
    output_path_zich = render_layout(perm_str, "zich", 1, num_z)
    perm_output_paths.append(output_path_zich)
    
    # 3. Z-File mode (single z-dimension item per file)
    z_dimension = permutation[2]  # Get the z-dimension name
    
    # Get the actual keys for z-dimension (not titles) using sorted keys
    sorted_z_keys = query_keys(sorted_keys, permutation, permutation[2])
    
    for z_idx, z_key in enumerate(sorted_z_keys):
        # Create single z-item data view
        single_z_data_view = {z_key: data_view[z_key]}
        is_z_band = (z_dimension == 'B')

        def format_band_key(band_key):
            """Format band range key with zero-padded frequencies"""
            if '-' in band_key and 'Hz' in band_key:
                # Split on the dash
                parts = band_key.split('-')
                if len(parts) == 2:
                    start_part = parts[0].strip()
                    end_part = parts[1].strip()
                
                    # Extract frequency numbers
                    start_freq = start_part.replace('Hz', '')
                    end_freq = end_part.replace('Hz', '')
                
                    try:
                        # Convert to int and zero-pad to 5 digits
                        start_padded = f"{int(start_freq):05d}Hz"
                        end_padded = f"{int(end_freq):05d}Hz"
                        return f"{start_padded}-{end_padded}"
                    except ValueError:
                        # If conversion fails, return original
                        return band_key
            return band_key
        
        # Temporarily replace data_view for this z-item
        original_data_view = data_view
        data_view = single_z_data_view
        
        # Render single z-item file
        if is_z_band:
            formatted_z_key = format_band_key(z_key)
            z_filename = sanitize_filename(formatted_z_key.replace("::", "--"))
        else:
            z_filename = sanitize_filename(z_key.replace("::", "--"))
        output_filename = f"{perm_str}.{z_filename}.{full_filename}.png"
        
        # Use render_layout with single z-item setup
        resolved_config = get_config(perm_str, "zfile")
        resolved_config = resolved_config.copy()
        resolved_config["max_hgrid_cells_per_line"] = 999999
        resolved_config["max_vgrid_cells_per_column"] = 999999
        
        surface = DrawingSurface(
            grid_cols=num_x,
            grid_rows=num_y,
            intracell_cols=1,
            intracell_rows=1,
            legend_rows=0,
            legend_cols=0,
            config=resolved_config
        )
        
        # Get sorted keys for single z-item iteration
        sorted_y_keys = query_keys(sorted_keys, permutation, permutation[1])
        sorted_x_keys = query_keys(sorted_keys, permutation, permutation[0])
        
        # Draw single z-item data points using sorted keys
        for y_idx, y_key in enumerate(sorted_y_keys):
            for x_idx, x_key in enumerate(sorted_x_keys):
                # Check if this combination exists in the single z-item data
                if (y_key in data_view[z_key] and 
                    x_key in data_view[z_key][y_key]):
                    
                    data_point = data_view[z_key][y_key][x_key]
                    
                    # FIXED: Always determine which metric this data point represents
                    metric_key = None
                    if permutation[0] == 'M':
                        metric_key = x_key
                    elif permutation[1] == 'M':
                        metric_key = y_key
                    elif permutation[2] == 'M':
                        metric_key = z_key
                    
                    # FIXED: Always use metric index for coloring
                    if metric_key:
                        original_metric_idx = list(METRICS.keys()).index(metric_key)
                        color = get_color(original_metric_idx, data_point['value'], data_point['bipolar'], num_metrics)
                    else:
                        # Fallback (shouldn't happen if metrics are in one of the dimensions)
                        color = (128, 128, 128)  # Gray fallback
                    
                    # Draw datapoint (always page 0, no intracell positioning)
                    surface.draw_datapoint(0, x_idx, y_idx, 0, 0, color)
        
        # FIXED: Prepare single z-item color indicator - always based on metrics
        if permutation[0] == 'M' or permutation[1] == 'M' or permutation[2] == 'M':
            # Find which metric this z-file represents
            if z_dimension == 'M':
                # Z-dimension is metrics - use the specific metric for this file
                metric_config = METRICS[z_key]
                is_bipolar = metric_config["type"] == "bipolar"
                original_metric_idx = list(METRICS.keys()).index(z_key)
                color_metric_idx = original_metric_idx
                total_metrics = num_metrics
            else:
                # Z-dimension is not metrics, but we still have metrics in X or Y
                # Use representative metric colors based on actual data
                has_bipolar = any(METRICS[key]["type"] == "bipolar" for key in METRICS.keys())
                is_bipolar = has_bipolar
                color_metric_idx = 0  # Use first metric's color scheme
                total_metrics = num_metrics
        else:
            # No metrics in any dimension (shouldn't happen)
            is_bipolar = False
            color_metric_idx = 0
            total_metrics = 1
        
        min_value = -1.0 if is_bipolar else 0.0
        max_value = 1.0
        
        min_color = get_color(color_metric_idx, min_value, is_bipolar, total_metrics)
        max_color = get_color(color_metric_idx, max_value, is_bipolar, total_metrics)
        z_info = [{
            'metric_index': color_metric_idx,
            'min_color': min_color,
            'max_color': max_color,
            'grid_position': color_metric_idx
        }]
                
        # Draw color indicators (z-file mode)
        surface.draw_metric_color_indicators(0, "z-file", "zfile", z_info)
        
        # Draw grid lines
        surface.draw_grid_lines(0)
        
        # Draw labels (no minor labels since intracell = 1)
        for x_idx in range(len(x_labels) - 1, -1, -1):
            surface.draw_hlabel_strip(0, x_idx, x_labels[x_idx])
        
        for y_idx in range(len(y_labels)):
            surface.draw_vlabel_strip(0, y_idx, y_labels[y_idx])
        
        # Draw title for Z-file mode
        if z_dimension == 'M':
            # For metrics, use the title from METRICS config
            z_title = METRICS[z_key]["title"]
        else:
            # For non-metrics, use the key as title
            z_title = z_key
        surface.draw_title(z_title)
        
        # Save single z-item image
        output_path = os.path.join(out_path, "fingerprint", output_filename)
        surface.save(output_path)
        perm_output_paths.append(output_path)
        
        # Restore original data_view
        data_view = original_data_view    
    
    result['output_paths'] = perm_output_paths
    result['permutation'] = perm_str
    
    # print(f"Permutation: {perm_str}")
    # print(f"Sorted band keys: {query_keys(sorted_keys, permutation, 'B')}")
    # print(f"x_labels: {x_labels}")
    # print(f"y_labels: {y_labels}")
    # print(f"z_labels: {z_labels}")

    return result

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    """Main process function - generates fingerprint images for all permutations"""
    result = {}
    
    # Create fingerprint subdirectory under out_path
    fingerprint_dir = os.path.join(out_path, "fingerprint")
    os.makedirs(fingerprint_dir, exist_ok=True)
    
    # Initialize CSS-like configuration system
    init_config(config_dict=CONFIG_RULES)
    
    # Define all possible permutations
    permutations = ["btm", "bmt", "tbm", "tmb", "mbt", "mtb"]
    #permutations = ["btm"]
    
    # Process each permutation
    all_output_paths = []
    permutation_results = {}
    
    for perm_str in permutations:
        try:
            perm_result = process_permutation(file_path, out_path, config, previous, perm_str)
            all_output_paths.extend(perm_result['output_paths'])
            permutation_results[perm_str] = perm_result
        except Exception as e:
            print(f"Error processing permutation {perm_str}: {e}")
            permutation_results[perm_str] = {'error': str(e), 'output_paths': []}
    
    result['output_paths'] = all_output_paths
    result['fingerprint_dir'] = fingerprint_dir
    result['permutation_results'] = permutation_results
    
    return {"result": result}