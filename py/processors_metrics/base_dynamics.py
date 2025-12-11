ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
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
    # config_scope = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.scope", selector = None).to_graph()
    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()

    # assert (channels := config_scope["channels"]) is not None
    # assert (time_split := config_scope["time_split"]) is not None
    # assert (band_split := config_scope["time_split"]) is not None

    low_hz = int(config_multiband.get("cutoff_low_freqHz", 200))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 21000))
    bands = int(config_multiband.get("bands", 6))
    
    frame_ms = int(config.get("frame_ms", 200))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_frame_ms": frame_ms,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
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
        'frame_ms': frame_ms,
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

def peak_dbfs(signal: np.ndarray) -> float:
   peak = np.max(np.abs(signal))
   if peak == 0:
       return -np.inf
   return 20 * np.log10(peak)

def analyze_band_dynamics(band_signal, frame_ms, rate, chunk, range_key):
    """Analyze dynamics for a single frequency band"""

    frame_size = int(rate * frame_ms / 1000.0)
       
    # Calculate frame-by-frame metrics
    frame_peaks = []
    frame_rms = []
       
    for i in range(0, len(band_signal), frame_size):
        frame = band_signal[i:i+frame_size]
        if len(frame) == 0:
            continue
               
        frame_peak = np.max(np.abs(frame))
        frame_rms_val = np.sqrt(np.mean(frame ** 2))
           
        if frame_peak > 0:
            frame_peaks.append(frame_peak)
        if frame_rms_val > 0:
            frame_rms.append(frame_rms_val)
       
    # Overall band metrics
    band_peak_dbfs = peak_dbfs(band_signal)
    band_rms_dbfs = rms_dbfs(band_signal)
       
    # Crest factor (peak to RMS ratio)
    if band_rms_dbfs != -np.inf and band_peak_dbfs != -np.inf:
        crest_factor_db = band_peak_dbfs - band_rms_dbfs
    else:
        crest_factor_db = None
       
    # Dynamic range metrics from frame analysis
    if frame_peaks and frame_rms:
        # Calculate all metrics in one pass
        min_peak = np.min(frame_peaks)
        max_peak = np.max(frame_peaks)
        min_rms = np.min(frame_rms)
        max_rms = np.max(frame_rms)
    
        # Dynamic range calculations
        if min_peak > 1e-12:
            peak_dyn_range_db = 20 * np.log10(max_peak / min_peak)
        else:
            peak_dyn_range_db = min(120.0, 20 * np.log10(max_peak / 1e-12))
    
        if min_rms > 1e-12:
            rms_dyn_range_db = 20 * np.log10(max_rms / min_rms)
        else:
            rms_dyn_range_db = min(120.0, 20 * np.log10(max_rms / 1e-12))
    
        # Crest factor calculations
        frame_crest_factors_db = [20 * np.log10(peak / max(rms, 1e-12)) 
                                for peak, rms in zip(frame_peaks, frame_rms)]
        avg_crest_factor_db = np.mean(frame_crest_factors_db) if frame_crest_factors_db else None
        std_crest_factor_db = np.std(frame_crest_factors_db) if len(frame_crest_factors_db) > 1 else None

    else:
        peak_dyn_range_db = None
        rms_dyn_range_db = None
        avg_crest_factor_db = None
        std_crest_factor_db = None

    return {
        "chunk": chunk,
        "peak_dbfs": round(band_peak_dbfs, 2) if band_peak_dbfs != -np.inf else None,
        "rms_dbfs": round(band_rms_dbfs, 2) if band_rms_dbfs != -np.inf else None,
        "crest_factor_db": round(crest_factor_db, 2) if crest_factor_db is not None else None,
        "peak_dyn_range_db": round(peak_dyn_range_db, 2) if peak_dyn_range_db is not None else None,
        "rms_dyn_range_db": round(rms_dyn_range_db, 2) if rms_dyn_range_db is not None else None,
        "avg_crest_factor_db": round(avg_crest_factor_db, 2) if avg_crest_factor_db is not None else None,
        "std_crest_factor_db": round(std_crest_factor_db, 2) if std_crest_factor_db is not None else None
    }

def process_single_chunk(chunk_path, chunk, frame_ms, log_edges, bands):
    data, rate = sf.read(chunk_path)
    if data.ndim > 1:
        data = np.mean(data, axis=1)  # Convert to mono
            
    # Process each frequency band
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

        # Bandpass filter for this frequency range
        band_signal = bandpass(data, rate, f_low, f_high)
            
        # Analyze dynamics for this band
        band_result = analyze_band_dynamics(band_signal, frame_ms, rate, chunk, range_key)
        result[range_key] = band_result
    
    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['frame_ms'], ctx['log_edges'], ctx['bands'])

