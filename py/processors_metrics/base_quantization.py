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

    low_hz = int(config_multiband.get("cutoff_low_freqHz", 200))
    high_hz = int(config_multiband.get("cutoff_high_freqHz", 21000))
    bands = int(config_multiband.get("bands", 6))

    frame_size = int(config.get("frame_size", 2048))
    bit_depth_tolerance = float(config.get("bit_depth_tolerance", 1e-7))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_low_hz": low_hz, 
        "_c_high_hz": high_hz, 
        "_c_bands": bands, 
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_frame_size": frame_size,
        "_c_bit_depth_tolerance": bit_depth_tolerance,
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
        'frame_size': frame_size,
        'bit_depth_tolerance': bit_depth_tolerance,
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

def estimate_bit_depth(signal, tolerance=1e-6):
   """Estimate effective bit depth by analyzing quantization levels"""
   # Remove DC offset
   signal = signal - np.mean(signal)
   
   # Find unique amplitude levels (with tolerance for floating point precision)
   unique_levels = []
   sorted_signal = np.sort(np.abs(signal[signal != 0]))  # Remove zeros and sort
   
   if len(sorted_signal) == 0:
       return None, 0
   
   current_level = sorted_signal[0]
   unique_levels.append(current_level)
   
   for sample in sorted_signal[1:]:
       if abs(sample - current_level) > tolerance:
           unique_levels.append(sample)
           current_level = sample
   
   # Estimate bit depth from number of unique levels
   num_levels = len(unique_levels)
   if num_levels <= 1:
       return None, num_levels
   
   estimated_bits = np.log2(num_levels * 2)  # *2 because we only counted positive levels
   return estimated_bits, num_levels

def calculate_noise_floor(magnitude_spectrum, percentile=10):
   """Calculate noise floor from FFT spectrum"""
   # Use lower percentile of spectrum as noise floor estimate
   noise_floor_db = np.percentile(magnitude_spectrum, percentile)
   if noise_floor_db <= 0:
       return -120.0  # Very low floor
   return 20 * np.log10(noise_floor_db)

def detect_quantization_artifacts(signal, frame_size=1024):
   """Detect quantization artifacts using spectral analysis"""
   artifacts = []
   
   for i in range(0, len(signal) - frame_size, frame_size // 2):
       frame = signal[i:i+frame_size]
       
       # Remove DC
       frame = frame - np.mean(frame)
       
       if np.std(frame) == 0:
           continue
           
       # FFT analysis
       windowed = frame * np.hanning(frame_size)
       fft_mag = np.abs(np.fft.fft(windowed))
       
       # Look for quantization noise patterns
       # Quantization creates broadband noise floor
       noise_floor = calculate_noise_floor(fft_mag)
       
       # Calculate spectral slope (quantization noise is typically flat)
       freqs = np.arange(len(fft_mag))
       # Focus on mid-to-high frequencies where quantization noise is most apparent
       mid_idx = len(fft_mag) // 4
       high_idx = len(fft_mag) // 2
       
       if high_idx > mid_idx:
           mid_energy = np.mean(fft_mag[mid_idx:high_idx])
           high_energy = np.mean(fft_mag[high_idx:])
           
           if mid_energy > 0 and high_energy > 0:
               spectral_slope = 20 * np.log10(high_energy / mid_energy)
           else:
               spectral_slope = -60.0  # Default steep slope
       else:
           spectral_slope = -60.0
           
       artifacts.append({
           'noise_floor_db': noise_floor,
           'spectral_slope_db': spectral_slope
       })
   
   return artifacts

def analyze_band_quantization(band_signal, frame_size, bit_depth_tolerance, chunk, range_key):
    """Analyze quantization for a single frequency band"""
    # Estimate bit depth
    est_bits, num_levels = estimate_bit_depth(band_signal, bit_depth_tolerance)
       
    # Detect quantization artifacts
    artifacts = detect_quantization_artifacts(band_signal, frame_size)
       
    if artifacts:
        avg_spectral_slope = np.mean([a['spectral_slope_db'] for a in artifacts])
        std_spectral_slope = np.std([a['spectral_slope_db'] for a in artifacts])
    else:
        avg_spectral_slope = None
        std_spectral_slope = None
       
    return {
        "chunk": chunk,
        "estimated_bits": round(est_bits, 2) if est_bits is not None else None,
        "unique_levels": num_levels,
        "avg_spectral_slope_db": round(avg_spectral_slope, 2) if avg_spectral_slope is not None else None,
        "std_spectral_slope_db": round(std_spectral_slope, 2) if std_spectral_slope is not None else None,
    }

def process_single_chunk(chunk_path, chunk, frame_size, bit_depth_tolerance, log_edges, bands):
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
            
        # Analyze quantization for this band
        band_result = analyze_band_quantization(band_signal, frame_size, bit_depth_tolerance, chunk, range_key)
        result[range_key] = band_result

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['frame_size'], ctx['bit_depth_tolerance'], ctx['log_edges'], ctx['bands'])

