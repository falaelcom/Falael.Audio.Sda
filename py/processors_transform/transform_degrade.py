ALGO_VERSION = "v024" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import numpy as np

import processors_transform.partition as partition

from zulu.fs_cache_utils import get_file_timestamps, get_keys
from zulu.parallel_dynamic_queue import parallel_dynamic_queue
from collections import deque

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

# Import the async processing module
from processors_transform.zulu.transform_degrade_async import process_chunk_callback

def progress_callback(item, result, stats, ctx):
    """Progress callback to show completion status"""
    ctx['completed_count'] += 1
    total_time_ms = stats['total_processing_time_ms']
    
    # Convert to mm:ss.msm format
    total_seconds = total_time_ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    
    print(f"Chunk {ctx['completed_count']} of {ctx['total_chunks']} completed in {minutes:02d}:{seconds:06.3f}")

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:
    """
    Parallel chunk-based reverb application with frequency-selective processing.
    
    Processes pre-split audio chunks in parallel, applies reverb to each chunk,
    saves processed chunks to disk.
    """

    chunks_source_processor_name = (pipeline_options or {}).get("chunks_source_processor_name", partition.PROCESSOR_NAME)
    assert (chunks_root := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["dir_name"])
    assert (chunk_list := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["file_names"])
    assert (chunk_duration_sec := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["chunk_duration_sec"])

    configJSCSS = profile.load_config()
    
    config_parallel_forEach = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.parallel_forEach", selector = None).to_graph()
    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()
    config_multiband = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.multiband", selector = None).to_graph()

    # Global reverb parameters
    room_width = float(config.get("room_width", 15.0))
    room_height = float(config.get("room_height", 8.0))
    room_depth = float(config.get("room_depth", 25.0))
    num_comb_filters = int(config.get("num_comb_filters", 6))
    num_allpass_filters = int(config.get("num_allpass_filters", 3))
    pre_delay_ms = float(config.get("pre_delay_ms", 50.0))
    wet_dry_mix = float(config.get("wet_dry_mix", 0.5))
    
    # Cascade flag - enables iterative multi-reverb processing
    cascade_mode = bool(config.get("cascade_mode", False))
    
    # Frequency band parameters
    low_hz = int(config_multiband.get("cutoff_low_freqHz", 20))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 21000))
    bands = int(config_multiband.get("bands", 1))
    
    # Per-band reverb configurations
    band_configs = config.get("band_configs", [])
    default_band_config = config.get("default_band_config", {
        "rt60": 2.5,
        "absorption": 0.1,
        "stereo_decorrelation": 0.3
    })
    # Ensure we have config for each band
    while len(band_configs) < bands:
        band_configs.append(default_band_config)
    
    # Microphone positioning parameters
    mic_spacing_m = float(config.get("mic_spacing_m", 0.2))  # 20cm typical stereo pair

    signal_noise_config = config.get("signal_noise_config")
    reverb_enabled = config.get("reverb_enabled", True)
    signal_noise_enabled = config.get("signal_noise_enabled", True)
    processed_filename_prefix = 'reverb.'

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_signal_noise_config": signal_noise_config,
        "_c_reverb_enabled": reverb_enabled,
        "_c_signal_noise_enabled": signal_noise_enabled,
        "_c_processed_filename_prefix": processed_filename_prefix,
        "_c_chunks_source_processor_name": chunks_source_processor_name,
        "_c_room_width": room_width,
        "_c_room_height": room_height,
        "_c_room_depth": room_depth,
        "_c_num_comb_filters": num_comb_filters,
        "_c_num_allpass_filters": num_allpass_filters,
        "_c_pre_delay_ms": pre_delay_ms,
        "_c_wet_dry_mix": wet_dry_mix,
        "_c_low_hz": low_hz,
        "_c_high_hz": high_hz,
        "_c_bands": bands,
        "_c_band_configs": band_configs,
        "_c_cascade_mode": cascade_mode,
        "_c_mic_spacing_m": mic_spacing_m,
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list)
    })
    
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))
    
    # Parallel processing parameters
    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    use_processes = bool(config_parallel_forEach.get("use_processes", True))
    
    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)
    
    print(f"Processing {len(chunk_list)} chunks with {bands} frequency band(s)...")
    print(f"Cascade mode: {'ENABLED' if cascade_mode else 'DISABLED'}")
    print(f"Room dimensions: {room_width}m x {room_height}m x {room_depth}m")
    print(f"Wet/Dry: {wet_dry_mix}")
    
    # Create initial queue of chunk objects with iteration counts
    initial_queue = deque()
    for chunk_index, chunk_filename in enumerate(chunk_list):
        if cascade_mode:
            iteration_count = chunk_index + 1  # Chunk 0 gets 1, Chunk 1 gets 2, etc.
        else:
            iteration_count = 1  # All chunks get 1 iteration
        
        chunk_obj = {
            'chunk_index': chunk_index,
            'chunk_filename': chunk_filename,
            'chunk_root': chunks_root,  # Original location
            'iteration_count': iteration_count,
            'is_first_processing': True
        }
        initial_queue.append(chunk_obj)
    
    # Create context for chunk processing
    context = {
        'signal_noise_config': signal_noise_config,
        'reverb_enabled': reverb_enabled,
        'signal_noise_enabled': signal_noise_enabled,
        'internal_storage': internal_storage,
        'processor_name': PROCESSOR_NAME,
        'algo_version': ALGO_VERSION,
        'params_version': new_params_version,
        'processed_filename_prefix': processed_filename_prefix, 
        'log_edges': log_edges,
        'band_configs': band_configs,
        'room_width': room_width,
        'room_height': room_height,
        'room_depth': room_depth,
        'num_comb_filters': num_comb_filters,
        'num_allpass_filters': num_allpass_filters,
        'pre_delay_ms': pre_delay_ms,
        'wet_dry_mix': wet_dry_mix,
        'cascade_mode': cascade_mode,
        'mic_spacing_m': mic_spacing_m,
        'completed_count': 0,
        'total_chunks': len(chunk_list)
    }
    
    # Process all chunks using dynamic queue
    parallel_dynamic_queue(
        initial_queue,
        process_chunk_callback,
        lambda item, result, stats: progress_callback(item, result, stats, context),
        context, 
        max_workers, 
        use_processes=use_processes
    )
    
    # Build processed chunk filenames using context prefix
    processed_filename_prefix = context['processed_filename_prefix']
    processed_chunks = [f"{processed_filename_prefix}{chunk_filename}" for chunk_filename in chunk_list]
    
    # Get output root directory
    out_root = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)
    # output_chunks_root = os.path.relpath(out_root, ".") # was relatiove
    output_chunks_root = os.path.abspath(out_root) # now is a full path
    
    print(f"Processing complete! {len(processed_chunks)} chunks processed.")
    
    data = {
        "params_version": new_params_version, 
        "params": params,
        "result": {
            "chunk_duration_sec": chunk_duration_sec,
            "dir_name": output_chunks_root,
            "file_names": processed_chunks,
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }