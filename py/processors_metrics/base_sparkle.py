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
    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()

    low_hz = int(config_multiband.get("cutoff_low_freqHz", 2000))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 20000))
    bands = int(config_multiband.get("bands", 4))

    frame_ms = int(config.get("frame_ms", 20))
    min_frequency_hz = int(config.get("min_frequency_hz", 2000))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_frame_ms": frame_ms,
        "_c_min_frequency_hz": min_frequency_hz,
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

    # Calculate total octaves for compensation
    total_octaves = np.log2(high_hz / low_hz)

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Create context object for callback
    context = {
        'frame_ms': frame_ms,
        'log_edges': log_edges,
        'bands': bands,
        'min_frequency_hz': min_frequency_hz,
        'total_octaves': total_octaves
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

def transient_rms(signal, frame_size):
    frame_energy = []
    for i in range(0, len(signal), frame_size):
        frame = signal[i:i+frame_size]
        if len(frame) == 0:
            continue
        rms = np.sqrt(np.mean(np.square(frame)))
        frame_energy.append(rms)
    return np.mean(frame_energy) if frame_energy else 0.0

def process_single_chunk(chunk_path, chunk, frame_ms, log_edges, bands, min_frequency_hz, total_octaves):
    data, rate = sf.read(chunk_path)
    if data.ndim == 1:
        signal = data
    else:
        signal = np.mean(data, axis=1)

    frame_size = int(rate * frame_ms / 1000.0)

    # Process each frequency band
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

        # Check if this frequency band is below 2kHz
        if f_high < min_frequency_hz:
            # No sparkle in low frequency bands
            sparkle_value = 0.0
        else:
            band_signal = bandpass(signal, rate, f_low, f_high)
                
            # Apply normalization to prevent overflow
            max_val = np.max(np.abs(band_signal))
            if max_val > 1.0:
                band_signal = band_signal / max_val
                
            sparkle_value = transient_rms(band_signal, frame_size)

        # Add compensation for band width
        if sparkle_value > 0:
            band_octaves = np.log2(f_high / f_low)
            compensation_factor = total_octaves / band_octaves
            sparkle_value_compensated = sparkle_value * compensation_factor
        else:
            sparkle_value_compensated = sparkle_value

        result[range_key] = {
            "chunk": chunk,
            "sparkle": round(float(sparkle_value_compensated), 6)
        }

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['frame_ms'], ctx['log_edges'], 
                               ctx['bands'], ctx['min_frequency_hz'], ctx['total_octaves'])

