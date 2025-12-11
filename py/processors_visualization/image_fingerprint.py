ALGO_VERSION = "v014" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

from gc import enable
import os
import spectra

from zulu.fs_cache_utils import get_file_timestamps, get_keys, sanitate_params
from zulu.parallel_forEach_collection import parallel_forEach_collection

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

from .image_fingerprint_zulu.data_regrouping import get_data_view, query_keys
from .image_fingerprint_zulu.drawing_surface import DrawingSurface

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})
    
    config_parallel_forEach = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.parallel_forEach", selector = None).to_graph()
    configJSCSS_metric_keys_render = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.METRIC_KEYS_RENDER", selector = None)
    metrics_keys_render = configJSCSS_metric_keys_render.to_graph()
    
    configJSCSS_metrics_all = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.METRICS_ALL", selector = None)
    metrics_all = configJSCSS_metrics_all.to_graph()

    configJSCSS_styles = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.STYLES_FINGERPRINT", selector = None)
    styles = configJSCSS_styles.to_graph()

    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()
    image_types = config.get("image_types", None)
    
    # Define permutations based on image_types or default to all
    if image_types is None:
        permutations = ["btm", "bmt", "tbm", "tmb", "mbt", "mtb"]
    else:
        # Extract unique permutations from image_types (first element of each pair)
        permutations = list({pair[0] for pair in image_types if pair[0] in ["btm", "bmt", "tbm", "tmb", "mbt", "mtb"]})

    key = {
        "_c_algo_ver": ALGO_VERSION,

        "_c_image_types": image_types,
        "_c_metrics_keys_render": metrics_keys_render,
        "_c_styles": styles
    }
    metrics_data = {}
    for metric_idx, metric_full_name in enumerate(metrics_keys_render.keys()):
        if not metrics_keys_render[metric_full_name]: continue
        processor_name, field_name = metric_full_name.split("::")
        if processor_name in key: continue
        metrics_all[metric_full_name]["normalize_func"] = None
        key[metric_full_name] = {
            "params": session_data[processor_name]["params"],
            "norm": metrics_all[metric_full_name],
        }
        metrics_data[processor_name] = session_data[processor_name]

    (params, new_params_version) = get_keys(key)
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))
    image_root = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)
    os.makedirs(image_root, exist_ok=True)
    
    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    assert (use_processes := config_parallel_forEach["use_processes"]) is not None
    assert (enable_parallel := config_parallel_forEach["enable"]) is not None

    context = {
        'file_path': file_path,
        'internal_storage': internal_storage,
        'new_params_version': new_params_version,
        'profile': profile,
        'metrics_data': metrics_data,
        'image_types': image_types,
        'pipeline_options': pipeline_options
    }
    
    # Process all permutations in parallel
    perm_results = parallel_forEach_collection(
        permutations, 
        _process_single_permutation, 
        context, 
        max_workers, 
        use_processes=use_processes,
        enable_parallel=enable_parallel
    )
    
    # Transform results back into expected schema
    all_output_paths = []
    
    for i, perm_result in enumerate(perm_results):
        all_output_paths.extend([os.path.basename(path) for path in perm_result['output_paths']])
    
    data = {
        "params_version": new_params_version, 
        "params": sanitate_params(params, once=['_c_chunk_duration_sec', '_c_chunks', 'base_quantization', '_c_low_hz', '_c_high_hz', '_c_bands']), 
        "result": {
            "dir_name": image_root,
            "file_names": all_output_paths,
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }

def process_permutation(file_path: str, internal_storage: InternalStorage, new_params_version: str, profile: ConfigCompositeProfile, metrics_data: dict, perm_str: str, image_types: dict, pipeline_options: dict) -> dict:
    """Process a single permutation and generate fingerprint images"""

    out_path = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    configJSCSS_styles = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.STYLES_FINGERPRINT", selector = None)
    styles = configJSCSS_styles.to_graph()

    configJSCSS_metrics_all = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.METRICS_ALL", selector = None)
    metrics_all = configJSCSS_metrics_all.to_graph()

    configJSCSS_metric_keys_render = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.METRIC_KEYS_RENDER", selector = None)
    metrics_keys_render = configJSCSS_metric_keys_render.to_graph()
    
    metrics = {
        key: metrics_all[key] 
        for key in metrics_keys_render 
        if metrics_keys_render[key] and key in metrics_all
    }

    if not len(metrics): raise ValueError(f"{PROCESSOR_NAME}.METRIC_KEYS_RENDER is empty.")

    config_partition_sub_time_split = configJSCSS.query(path_filter = "partition_sub_time_split", selector = None).to_graph()
    chunk_duration_sec = config_partition_sub_time_split.get("chunk_duration_sec", 30.0)

    result = {}
    
    # Convert permutation string to list
    permutation = permutation_string_to_list(perm_str)

    data_view, sorted_keys = get_data_view(metrics_data, permutation, metrics, chunk_duration_sec)
    
    # Get labels using sorted keys
    metric_labels = [metrics[key]["title"] for key in metrics.keys()]
    
    # Calculate dimensions
    num_metrics = len(metrics)
    
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
        styles = configJSCSS_styles.query(selector = layout_name + "." + z_mode).to_graph()
        
        # Create drawing surface
        surface = DrawingSurface(
            grid_cols=num_x,
            grid_rows=num_y,
            intracell_cols=intracell_cols,
            intracell_rows=intracell_rows,
            legend_rows=0,
            legend_cols=0,
            config=styles
        )
        
        # Get wrapping configuration
        if z_mode == "zicv":
            max_cells_per_page = styles["max_hgrid_cells_per_line"]
        else:  # zich
            max_cells_per_page = styles["max_vgrid_cells_per_column"]
        
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
                            original_metric_idx = list(metrics.keys()).index(metric_key)
                            color = get_color(original_metric_idx, data_point['value'], data_point['polarity'], num_metrics)
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
        
        indicators_info = []
        
        if permutation[0] == 'M':
            # X-dimension is metrics - indicators span full grid cells horizontally
            for metric_idx, metric_key in enumerate(metrics.keys()):
                metric_config = metrics[metric_key]
                
                # Determine min/max values based on metric polarity
                if metric_config["polarity"] in ["bipolar", "tripolar"]:
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["polarity"], num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["polarity"], num_metrics)
                
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
            for metric_idx, metric_key in enumerate(metrics.keys()):
                metric_config = metrics[metric_key]
                
                # Determine min/max values based on metric polarity
                if metric_config["polarity"] in ["bipolar", "tripolar"]:
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["polarity"], num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["polarity"], num_metrics)
                
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
            for metric_idx, metric_key in enumerate(metrics.keys()):
                metric_config = metrics[metric_key]
                
                # Determine min/max values based on metric polarity
                if metric_config["polarity"] in ["bipolar", "tripolar"]:
                    min_value = -1.0
                    max_value = 1.0
                else:  # unipolar
                    min_value = 0.0
                    max_value = 1.0
                
                # Generate min/max colors
                min_color = get_color(metric_idx, min_value, metric_config["polarity"], num_metrics)
                max_color = get_color(metric_idx, max_value, metric_config["polarity"], num_metrics)
                
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
        
        # Save image
        output_filename = f"{perm_str}.{z_mode}.{full_filename}.png"
        output_path = os.path.join(out_path, output_filename)
        surface.save(output_path)
        
        return output_path
    
    perm_output_paths = []
    
    # Render only the modes specified in image_types or all if None
    # Get allowed modes for this permutation
    allowed_modes = []
    if image_types is None:
        allowed_modes = ["zicv", "zich", "zfile"]
    else:
        allowed_modes = [pair[1] for pair in image_types if pair[0] == perm_str and pair[1] in ["zicv", "zich", "zfile"]]

    # 1. Z-Intracell-Vertical (zicv)
    if "zicv" in allowed_modes:
        output_path_zicv = render_layout(perm_str, "zicv", num_z, 1)
        perm_output_paths.append(output_path_zicv)
    
    # 2. Z-Intracell-Horizontal (zich)
    if "zich" in allowed_modes:
        output_path_zich = render_layout(perm_str, "zich", 1, num_z)
        perm_output_paths.append(output_path_zich)
    
    # 3. Z-File mode (zfile)
    if "zfile" in allowed_modes:
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
            styles = configJSCSS_styles.query(selector = perm_str + "." + "zfile").to_graph()
            styles["max_hgrid_cells_per_line"] = 999999
            styles["max_vgrid_cells_per_column"] = 999999
            
            surface = DrawingSurface(
                grid_cols=num_x,
                grid_rows=num_y,
                intracell_cols=1,
                intracell_rows=1,
                legend_rows=0,
                legend_cols=0,
                config=styles
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
                            original_metric_idx = list(metrics.keys()).index(metric_key)
                            color = get_color(original_metric_idx, data_point['value'], data_point['polarity'], num_metrics)
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
                    metric_config = metrics[z_key]
                    metric_polarity = metric_config["polarity"]
                    original_metric_idx = list(metrics.keys()).index(z_key)
                    color_metric_idx = original_metric_idx
                    total_metrics = num_metrics
                else:
                    # Z-dimension is not metrics, but we still have metrics in X or Y
                    # Use representative metric colors based on actual data
                    has_tripolar = any(metrics[key]["polarity"] == "tripolar" for key in metrics.keys())
                    has_bipolar = any(metrics[key]["polarity"] == "bipolar" for key in metrics.keys())
                    has_polar = has_tripolar or has_bipolar
                    polarity_to_use = "tripolar" if has_tripolar else "bipolar" if has_bipolar else "unipolar"
                    color_metric_idx = 0  # Use first metric's color scheme
                    total_metrics = num_metrics
            
                if z_dimension == 'M':
                    if metric_polarity in ["bipolar", "tripolar"]:
                        min_value = -1.0
                    else:
                        min_value = 0.0
                else:
                    if has_polar:
                        min_value = -1.0
                    else:
                        min_value = 0.0
                
                max_value = 1.0
                
                min_color = get_color(color_metric_idx, min_value, polarity_to_use if z_dimension != 'M' else metric_polarity, total_metrics)
                max_color = get_color(color_metric_idx, max_value, polarity_to_use if z_dimension != 'M' else metric_polarity, total_metrics)
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
                # For metrics, use the title from metrics config
                z_title = metrics[z_key]["title"]
            else:
                # For non-metrics, use the key as title
                z_title = z_key
            surface.draw_title(z_title)
            
            # Save single z-item image
            output_path = os.path.join(out_path, output_filename)
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

def get_color(metric_index, normalized_value, metric_polarity, num_metrics):
    """Generate color for metrics using LCH color space for proper vividness control"""
    
    if normalized_value is None: return (0, 0, 0)

    # Use second half spectrum (180-360 degrees) for primary colors
    primary_hue = 180 + (metric_index / num_metrics) * 180
    
    if metric_polarity == "bipolar":
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
    elif metric_polarity == "tripolar":
        spread = 130
        # -1 to 1 range: vivid primary at 0, subdued semi-complements at ±1
        semi_comp1_hue = (primary_hue - spread) % 360  # for -1
        semi_comp2_hue = (primary_hue + spread) % 360  # for +1
        
        # Define endpoint colors in LCH
        left_color = spectra.lch(30, 50, semi_comp1_hue)
        mid_color = spectra.lch(50, 100, primary_hue)
        right_color = spectra.lch(30, 50, semi_comp2_hue)
        
        # Blend based on value
        if normalized_value == 0:
            rgb = mid_color.clamped_rgb
        elif normalized_value < 0:
            ratio = -normalized_value  # 1 at -1, 0 at 0
            left_rgb = left_color.clamped_rgb
            mid_rgb = mid_color.clamped_rgb
            r = left_rgb[0] * ratio + mid_rgb[0] * (1 - ratio)
            g = left_rgb[1] * ratio + mid_rgb[1] * (1 - ratio)
            b = left_rgb[2] * ratio + mid_rgb[2] * (1 - ratio)
            rgb = (r, g, b)
        else:
            ratio = normalized_value  # 0 at 0, 1 at 1
            mid_rgb = mid_color.clamped_rgb
            right_rgb = right_color.clamped_rgb
            r = mid_rgb[0] * (1 - ratio) + right_rgb[0] * ratio
            g = mid_rgb[1] * (1 - ratio) + right_rgb[1] * ratio
            b = mid_rgb[2] * (1 - ratio) + right_rgb[2] * ratio
            rgb = (r, g, b)
        
        return (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
    else:
        # unipolar: 0 to 1 range: variable lightness with max chroma at value=1
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

def _process_single_permutation(perm_index, perm_str, context):
    """Process a single permutation - wrapper for parallel processing"""

    return process_permutation(
        context['file_path'], 
        context['internal_storage'], 
        context['new_params_version'],
        context['profile'], 
        context['metrics_data'], 
        perm_str,
        context['image_types'],
        context['pipeline_options']
    )