import numpy as np

def normalize_value(raw_value, norm_config):
    """Normalize a single value using the provided function"""
    normalized = norm_config["normalize_func"](raw_value, norm_config)
    return normalized, norm_config["type"] == "bipolar"

def get_data_view(previous: dict, dimensions: list, metric_normalization: dict, config: dict) -> dict:
    """
    Regroup and normalize data for visualization
    
    Args:
        previous: Raw data from analysis modules
        dimensions: [x_dim, y_dim, z_dim] e.g. ['B', 'T', 'M']
        metric_normalization: Normalization config for each metric
        config: General config (contains chunk_duration)
    
    Returns:
        Tree structure: z_key -> y_key -> x_key -> {value: float, bipolar: bool}
        Plus sorted key lists for each dimension
    """
    
    # Step 1: Flatten data to uniform objects
    data_objects = []
    
    # Get chunk duration from config
    chunk_duration = config.get("chunk_duration", 30.0)
    
    # Iterate through metrics in normalization config to maintain order
    for metric_idx, metric_full_name in enumerate(metric_normalization.keys()):
        # Parse metric name: "bucket::field"
        bucket_name, field_name = metric_full_name.split("::")
        
        # Get data for this metric bucket
        bucket_data = previous.get(bucket_name, {}).get("result", {})
        
        # Sort bands by their frequency range (extract start frequency for sorting)
        def extract_start_frequency(band_range):
            # Parse band range like "0-100" -> 0, "100-200" -> 100
            try:
                return float(band_range.split('-')[0])
            except:
                return 0.0
        
        sorted_bands = []
        for band_range, chunk_list in sorted(bucket_data.items(), key=lambda x: extract_start_frequency(x[0])):
            sorted_bands.append((band_range, chunk_list, band_range))
        
        for band_idx, (band_range, chunk_list, original_label) in enumerate(sorted_bands):
            for chunk_data in chunk_list:
                # Extract chunk number from filename
                chunk_filename = chunk_data["chunk"]
                chunk_number = int(chunk_filename.split(".")[-2])
                
                # Calculate time label
                start_time = chunk_number * chunk_duration
                end_time = (chunk_number + 1) * chunk_duration
                start_mm = int(start_time // 60)
                start_ss = int(start_time % 60)
                end_mm = int(end_time // 60)
                end_ss = int(end_time % 60)
                time_label = f"{start_mm:02d}:{start_ss:02d} - {end_mm:02d}:{end_ss:02d}"
                
                # Get raw value
                raw_value = chunk_data.get(field_name)
                if raw_value is None:
                    continue
                
                # Create data object
                data_obj = {
                    "key": {
                        "T": {"ordinal": chunk_number, "label": time_label},
                        "B": {"ordinal": band_idx, "label": band_range},
                        "M": {"ordinal": metric_idx, "label": metric_full_name}
                    },
                    "value": raw_value,
                    "metric_config": metric_normalization[metric_full_name]
                }
                data_objects.append(data_obj)
    
    # Step 2: Sort by permutation order (z, y, x)
    x_dim, y_dim, z_dim = dimensions
    
    def sort_key(obj):
        return (
            obj["key"][z_dim]["ordinal"],
            obj["key"][y_dim]["ordinal"], 
            obj["key"][x_dim]["ordinal"]
        )
    
    data_objects.sort(key=sort_key)
    
    # Step 3: Build tree structure z -> y -> x AND collect sorted keys from already-sorted data
    result_tree = {}
    
    # Collect keys in order from the sorted data_objects
    z_keys_ordered = []
    y_keys_ordered = []
    x_keys_ordered = []
    
    for obj in data_objects:
        z_key = obj["key"][z_dim]["label"]
        y_key = obj["key"][y_dim]["label"]
        x_key = obj["key"][x_dim]["label"]
        
        # Collect unique keys in the order they appear in sorted data
        if z_key not in z_keys_ordered:
            z_keys_ordered.append(z_key)
        if y_key not in y_keys_ordered:
            y_keys_ordered.append(y_key)
        if x_key not in x_keys_ordered:
            x_keys_ordered.append(x_key)
        
        # Normalize value
        normalized_value, is_bipolar = normalize_value(obj["value"], obj["metric_config"])
        
        # Create tree structure
        if z_key not in result_tree:
            result_tree[z_key] = {}
        if y_key not in result_tree[z_key]:
            result_tree[z_key][y_key] = {}
        
        result_tree[z_key][y_key][x_key] = {
            "value": normalized_value,
            "bipolar": is_bipolar
        }
    
    # Step 4: Return both tree and sorted keys (already in correct order)
    return result_tree, {
        z_dim: [original_label for _, _, original_label in sorted_bands] if z_dim == 'B' else z_keys_ordered,
        y_dim: [original_label for _, _, original_label in sorted_bands] if y_dim == 'B' else y_keys_ordered,
        x_dim: [original_label for _, _, original_label in sorted_bands] if x_dim == 'B' else x_keys_ordered
    }

def query_keys(sorted_keys_dict, permutation, dimension):
    """
    Get all keys for the given dimension, in sorted order.
    
    Args:
        sorted_keys_dict: Dictionary containing sorted keys for each dimension
        permutation: List like ['B', 'T', 'M'] defining the dimension mapping
        dimension: 'B', 'T', or 'M' - the dimension to get keys for
    
    Returns:
        List of keys for the dimension, sorted by ordinal
    """
    return sorted_keys_dict[dimension]