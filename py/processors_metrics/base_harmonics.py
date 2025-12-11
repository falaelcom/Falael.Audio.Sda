ALGO_VERSION = "v002" # increment to signal algo or output schema changes and invalidate current cache
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

    fft_size = int(config.get("fft_size", 2048))
    step_size = int(config.get("hop_size", 1024))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,
        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_fft_size": fft_size,
        "_c_step_size": step_size,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    assert (use_processes := config_parallel_forEach["use_processes"]) is not None

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Create context object for callback
    context = {
        'fft_size': fft_size,
        'step_size': step_size,
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

def spectral_flatness(mag_spectrum):
    mag_spectrum = np.where(mag_spectrum == 0, 1e-12, mag_spectrum)
    geo_mean = np.exp(np.mean(np.log(mag_spectrum)))
    arith_mean = np.mean(mag_spectrum)
    return geo_mean / arith_mean if arith_mean != 0 else 0

def normalized_spectral_centroid(band_signal, fft_size, step_size, sample_rate, f_low, f_high):
    """Calculate spectral centroid as fraction within the frequency band (0-1)"""
    centroid_fractions = []
    
    for i in range(0, len(band_signal) - fft_size, step_size):
        frame = band_signal[i:i+fft_size]
        windowed = frame * np.hanning(fft_size)
        
        fft = np.fft.rfft(windowed)
        magnitudes = np.abs(fft)
        frequencies = np.fft.rfftfreq(fft_size, 1/sample_rate)
        
        # Only consider frequencies within the band
        band_mask = (frequencies >= f_low) & (frequencies <= f_high)
        band_freqs = frequencies[band_mask]
        band_mags = magnitudes[band_mask]
        
        if len(band_mags) > 0 and np.sum(band_mags) > 0:
            centroid = np.sum(band_freqs * band_mags) / np.sum(band_mags)
            # Normalize to 0-1 within the band
            centroid_fraction = (centroid - f_low) / (f_high - f_low)
            centroid_fractions.append(np.clip(centroid_fraction, 0, 1))
    
    return np.mean(centroid_fractions) if centroid_fractions else None

def normalized_spectral_rolloff(band_signal, fft_size, step_size, sample_rate, f_low, f_high, rolloff_percent=0.85):
    """Calculate spectral rolloff as fraction within the frequency band (0-1)"""
    rolloff_fractions = []
    
    for i in range(0, len(band_signal) - fft_size, step_size):
        frame = band_signal[i:i+fft_size]
        windowed = frame * np.hanning(fft_size)
        
        fft = np.fft.rfft(windowed)
        magnitudes = np.abs(fft)
        frequencies = np.fft.rfftfreq(fft_size, 1/sample_rate)
        
        # Only consider frequencies within the band
        band_mask = (frequencies >= f_low) & (frequencies <= f_high)
        band_freqs = frequencies[band_mask]
        band_mags = magnitudes[band_mask]
        
        if len(band_mags) > 0 and np.sum(band_mags) > 0:
            cumulative = np.cumsum(band_mags**2)
            rolloff_threshold = rolloff_percent * cumulative[-1]
            rolloff_idx = np.where(cumulative >= rolloff_threshold)[0]
            
            if len(rolloff_idx) > 0:
                rolloff_freq = band_freqs[rolloff_idx[0]]
                # Normalize to 0-1 within the band
                rolloff_fraction = (rolloff_freq - f_low) / (f_high - f_low)
                rolloff_fractions.append(np.clip(rolloff_fraction, 0, 1))
    
    return np.mean(rolloff_fractions) if rolloff_fractions else None

def analyze_band_harmonics(band_signal, fft_size, step_size, sample_rate, f_low, f_high, chunk, range_key):
    """Analyze spectral characteristics for a single frequency band"""
    centroid_fractions = []
    rolloff_fractions = []
    flatness_values_pink = []
    
    center_freq = np.sqrt(f_low * f_high)  # Geometric mean for pink noise reference
    
    for i in range(0, len(band_signal) - fft_size, step_size):
        frame = band_signal[i:i+fft_size]
        windowed = frame * np.hanning(fft_size)
        
        fft = np.fft.rfft(windowed)
        magnitudes = np.abs(fft)
        frequencies = np.fft.rfftfreq(fft_size, 1/sample_rate)
        
        # Only consider frequencies within the band
        band_mask = (frequencies >= f_low) & (frequencies <= f_high)
        band_freqs = frequencies[band_mask]
        band_mags = magnitudes[band_mask]
        
        if len(band_mags) > 0 and np.sum(band_mags) > 0:
            # Spectral centroid
            centroid = np.sum(band_freqs * band_mags) / np.sum(band_mags)
            centroid_fraction = (centroid - f_low) / (f_high - f_low)
            centroid_fractions.append(np.clip(centroid_fraction, 0, 1))
            
            # Spectral rolloff
            cumulative = np.cumsum(band_mags**2)
            rolloff_threshold = 0.85 * cumulative[-1]
            rolloff_idx = np.where(cumulative >= rolloff_threshold)[0]
            if len(rolloff_idx) > 0:
                rolloff_freq = band_freqs[rolloff_idx[0]]
                rolloff_fraction = (rolloff_freq - f_low) / (f_high - f_low)
                rolloff_fractions.append(np.clip(rolloff_fraction, 0, 1))
            
            # Pink-noise-normalized spectral flatness
            pink_weights = band_freqs / center_freq  # Pink noise ~ 1/f slope
            weighted_mags = band_mags * pink_weights
            flatness_pink = spectral_flatness(weighted_mags)
            flatness_values_pink.append(flatness_pink)
    
    return {
        "chunk": chunk,
        "spectral_centroid_fraction": round(np.mean(centroid_fractions), 4) if centroid_fractions else None,    # no signal in the current band
        "spectral_rolloff_fraction": round(np.mean(rolloff_fractions), 4) if rolloff_fractions else None,    # no signal in the current band
        "spectral_flatness_ratio_pinkns_norm": round(np.mean(flatness_values_pink), 6) if flatness_values_pink else None,    # no signal in the current band
        "std_spectral_flatness_ratio_pinkns_norm": round(np.std(flatness_values_pink), 6) if flatness_values_pink else None    # no signal in the current band
    }

def process_single_chunk(chunk_path, chunk, fft_size, step_size, log_edges, bands):
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
            
        # Analyze spectral characteristics for this band
        band_result = analyze_band_harmonics(band_signal, fft_size, step_size, rate, f_low, f_high, chunk, range_key)
        result[range_key] = band_result
    
    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['fft_size'], ctx['step_size'], ctx['log_edges'], ctx['bands'])