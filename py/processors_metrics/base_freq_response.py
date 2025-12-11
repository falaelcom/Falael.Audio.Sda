ALGO_VERSION = "v004" # increment to signal algo or output schema changes and invalidate current cache
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

    low_hz = int(config_multiband.get("cutoff_low_freqHz", 100))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 20000))
    bands = int(config_multiband.get("bands", 8))

    fft_size = int(config.get("fft_size", 2048))
    overlap = float(config.get("overlap", 0.75))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_fft_size": fft_size,
        "_c_overlap": overlap,
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

    # Calculate total bandwidth for uniform distribution reference
    total_bandwidth = high_hz - low_hz

    # Create context object for callback
    context = {
        'fft_size': fft_size,
        'overlap': overlap,
        'log_edges': log_edges,
        'bands': bands,
        'low_hz': low_hz,
        'high_hz': high_hz,
        'total_bandwidth': total_bandwidth
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

def process_single_chunk(chunk_path, chunk, fft_size, overlap, log_edges, bands, low_hz, high_hz, total_bandwidth):
    data, rate = sf.read(chunk_path)
    if data.ndim > 1:
        data = np.mean(data, axis=1)  # Convert to mono

    # Calculate step size for overlap
    step_size = int(fft_size * (1 - overlap))
        
    # Collect all FFT frames for this chunk
    frames_ffts = []
    for i in range(0, len(data) - fft_size, step_size):
        frame = data[i:i+fft_size]
        windowed = frame * np.hanning(fft_size)
        fft_mag = np.abs(np.fft.rfft(windowed))
        frames_ffts.append(fft_mag)
        
    if not frames_ffts:
        raise ValueError("No frames processed")

    # Average across all frames
    avg_fft = np.mean(frames_ffts, axis=0)
        
    # Convert to frequency bins
    freqs = np.fft.rfftfreq(fft_size, 1/rate)
        
    # Calculate total energy in the analysis range (low_hz to high_hz)
    analysis_mask = (freqs >= low_hz) & (freqs <= high_hz)
    total_energy = np.sum(avg_fft[analysis_mask])
        
    # Prevent division by zero
    if total_energy == 0:
        total_energy = 1e-12
        
    # Calculate expected energy density for uniform distribution
    expected_energy_density = total_energy / total_bandwidth
        
    # Calculate relative balance for each band
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            
        # Find frequency bin indices for this band
        bin_mask = (freqs >= f_low) & (freqs <= f_high)
            
        if np.any(bin_mask):
            # Calculate band energy density (energy per Hz)
            band_energy = np.sum(avg_fft[bin_mask])
            band_width = f_high - f_low
            band_energy_density = band_energy / band_width
                
            # Calculate balance in dB (relative to uniform distribution)
            if band_energy_density > 0 and expected_energy_density > 0:
                balance_db = 20 * np.log10(band_energy_density / expected_energy_density)
            else:
                balance_db = -60.0  # Very low floor for empty bands

            # Calculate pink-normalized balance in dB (relative to equal energy per band)
            expected_band_energy_pink = total_energy / bands
            if band_energy > 0 and expected_band_energy_pink > 0:
                balance_db_norm = 20 * np.log10(band_energy / expected_band_energy_pink)
            else:
                balance_db_norm = -60.0  # Very low floor for empty bands
        else:
            balance_db = -60.0  # Very low floor for empty bands
            balance_db_norm = -60.0  # Very low floor for empty bands
            
        result[range_key] = {
            "chunk": chunk,
            "avg_magnitude_db": round(float(balance_db), 2),
            "avg_magnitude_db_pinkns_norm": round(float(balance_db_norm), 2)
        }
        
    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['fft_size'], ctx['overlap'], 
                               ctx['log_edges'], ctx['bands'], ctx['low_hz'], ctx['high_hz'], ctx['total_bandwidth'])
							   
							   