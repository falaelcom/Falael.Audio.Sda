ALGO_VERSION = "v010" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_transform.partition as partition

import numpy as np
import soundfile as sf

from zulu.bandpass_filter import bandpass
from zulu.fs_cache_utils import get_file_timestamps, get_keys
from zulu.parallel_forEach_chunkCollection import parallel_forEach_chunkCollection

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    chunks_source_processor_name = (pipeline_options or {}).get("chunks_source_processor_name", partition.PROCESSOR_NAME)
    assert (chunks_root := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["dir_name"])
    assert (chunk_list := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["file_names"])
    assert (chunk_duration_sec := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["chunk_duration_sec"])

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config_parallel_forEach = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.parallel_forEach", selector = None).to_graph()
    config_multiband = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.multiband", selector = None).to_graph()

    low_hz = int(config_multiband.get("cutoff_low_freqHz", 20))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 21000))
    bands = int(config_multiband.get("bands", 10))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list)
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    use_processes = config_parallel_forEach.get("use_processes", False)

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Create context object for callback
    context = {
        'log_edges': log_edges,
        'bands': bands
    }

    
    chunk_results = parallel_forEach_chunkCollection(_chunk_callback, chunk_list, chunks_root, context, max_workers, use_processes=use_processes)

    # Initialize output grouped by frequency ranges
    output = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
        output[range_key] = []

    # Distribute results to output bands
    for chunk_result in chunk_results:
        for range_key in output.keys():
            if range_key in chunk_result:
                output[range_key].append(chunk_result[range_key])

    data = {
        "params_version": new_params_version, 
        "params": params, 
        "result": output
    }
    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }

def rms_dbfs(signal: np.ndarray) -> float:
   rms = np.sqrt(np.mean(signal ** 2))
   if rms == 0:
       return -np.inf
   return 20 * np.log10(rms)

def process_mono_chunk(chunk, log_edges, bands):
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
        result[range_key] = {
            "chunk": chunk,
            "mid_rms": 0.0,
            "side_rms": 0.0,
            "width_ratio": 0.0,
            "presence": 0.0,
        }
    return result

def process_single_chunk(chunk_path, chunk, log_edges, bands):
    data, rate = sf.read(chunk_path)
    if data.ndim != 2 or data.shape[1] != 2:
        return process_mono_chunk(chunk, log_edges, bands)

    left = data[:, 0]
    right = data[:, 1]
        
    # Process each frequency band
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

        # Bandpass filter for this frequency range
        left_band = bandpass(left, rate, f_low, f_high)
        right_band = bandpass(right, rate, f_low, f_high)

        # Calculate Mid/Side from bandpassed signals
        mid = 0.5 * (left_band + right_band)
        side = 0.5 * (left_band - right_band)

        mid_rms = rms_dbfs(mid)
        side_rms = rms_dbfs(side)

        if mid_rms == -np.inf:
            width_ratio = 0.0
        else:
            width_ratio = 10 ** (side_rms / 20) / 10 ** (mid_rms / 20)

        # Calculate derived metrics from width_ratio
        if width_ratio is not None and not np.isnan(width_ratio):
            # Presence: exponential approach to 1.0 (saturation_point = 2.0)
            presence = 1 - np.exp(-width_ratio * 2.0 / 2.0)
                
        else:
            presence = None

        result[range_key] = {
            "chunk": chunk,
            "mid_rms": round(mid_rms, 2) if mid_rms != -np.inf else None,
            "side_rms": round(side_rms, 2) if side_rms != -np.inf else None,
            "width_ratio": round(float(width_ratio), 4) if not np.isnan(width_ratio) else None,
            "presence": round(float(presence), 4) if presence is not None else None,
        }

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['log_edges'], ctx['bands'])
