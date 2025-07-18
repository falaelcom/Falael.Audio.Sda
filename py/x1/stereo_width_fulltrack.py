import os
import numpy as np
import soundfile as sf
from scipy import signal
from lib.bandpass_filter import bandpass
from lib.parallel_collection_process import parallel_collection_process

def process_single_band(band_index, band_info, context):
    """Process a single frequency band for stereo width analysis"""
    f_low, f_high, band_key = band_info
    
    # Extract context
    left_channel = context['left_channel']
    right_channel = context['right_channel']
    sample_rate = context['sample_rate']
    window_samples = context['window_samples']
    noverlap = context['noverlap']
    
    # Step 1: Pre-filter entire track for this frequency band
    left_band = bandpass(left_channel, sample_rate, f_low, f_high)
    right_band = bandpass(right_channel, sample_rate, f_low, f_high)
    
    # Step 2: Convert to Mid/Side for the entire band-filtered signals
    mid_band = 0.5 * (left_band + right_band)
    side_band = 0.5 * (left_band - right_band)
    
    # Step 3: Apply STFT to Mid and Side signals for consistent windowing
    _, _, stft_mid = signal.stft(
        mid_band,
        fs=sample_rate,
        window='hann',           # Same window as freq_response_fulltrack
        nperseg=window_samples,  # Same window size
        noverlap=noverlap        # Same overlap
    )
    
    _, _, stft_side = signal.stft(
        side_band,
        fs=sample_rate,
        window='hann',
        nperseg=window_samples,
        noverlap=noverlap
    )
    
    # Step 4: Calculate width_ratio for each time frame
    num_frames = stft_mid.shape[1]
    width_ratios = []
    
    for frame_idx in range(num_frames):
        # Get magnitude spectrum for this frame
        mid_magnitude = np.abs(stft_mid[:, frame_idx])
        side_magnitude = np.abs(stft_side[:, frame_idx])
        
        # Calculate RMS from magnitude spectrum
        # RMS from frequency domain: sqrt(sum(|X|^2) / N)
        mid_rms = np.sqrt(np.mean(mid_magnitude ** 2))
        side_rms = np.sqrt(np.mean(side_magnitude ** 2))
        
        # Calculate width ratio
        if mid_rms > 0:
            width_ratio = side_rms / mid_rms
        else:
            width_ratio = 0.0
        
        width_ratios.append(width_ratio)
    
    # Return result for this band
    return {
        band_key: {
            "width_ratio": {
                "origin_value": 0.0,        # Will be set during compression
                "origin_sample": 0,         # First sample position
                "interval_samples": context['hop_samples'],  # Samples between each measurement
                "sample_rate": sample_rate, # For consumer time conversion
                "values": width_ratios      # Width ratio values
            }
        }
    }

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    """
    Calculate track-wide stereo width using sliding windows with identical timing to freq_response_fulltrack.
    
    Creates a dense time series showing stereo width (width_ratio) changes over time
    for each frequency band, with perfect temporal alignment for correlation analysis.
    
    Uses identical windowing parameters as freq_response_fulltrack for precise time matching.
    Optimized approach: pre-filter entire track per band, then apply STFT for consistent timing.
    """
    
    # Get configuration parameters - MUST match freq_response_fulltrack exactly
    window_samples = int(config.get("freq_response_fulltrack::window_samples", 4096))  # Same FFT window size
    hop_samples = int(config.get("freq_response_fulltrack::hop_samples", 2048))        # Same step between windows
    low_hz = int(config.get("multiband::cutoff_low_freqHz", 100))                     # Same frequency range
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))                 # Same frequency range
    bands = int(config.get("multiband::bands", 8))                                    # Same number of bands
    max_workers = config.get("parallel::max_workers", None)
    
    try:
        # Load the entire audio file
        data, sample_rate = sf.read(file_path)
        
        # Ensure we have stereo data
        if data.ndim != 2 or data.shape[1] != 2:
            return {"error": "Audio file must be stereo for stereo width analysis"}
        
        # Extract left and right channels
        left_channel = data[:, 0]
        right_channel = data[:, 1]
            
    except Exception as e:
        return {"error": f"Failed to load audio file: {str(e)}"}
    
    # Create identical logarithmic frequency bands as freq_response_fulltrack
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)
    
    # Calculate overlap for scipy STFT (must match freq_response_fulltrack)
    noverlap = window_samples - hop_samples
    
    # Prepare bands for parallel processing
    bands_to_process = []
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        band_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
        bands_to_process.append((f_low, f_high, band_key))
    
    # Create context object for parallel processing
    context = {
        'left_channel': left_channel,
        'right_channel': right_channel,
        'sample_rate': sample_rate,
        'window_samples': window_samples,
        'hop_samples': hop_samples,
        'noverlap': noverlap
    }
    
    # Process all bands in parallel
    band_results = parallel_collection_process(
        bands_to_process,
        process_single_band,
        context,
        max_workers,
        use_processes=False
    )
    
    # Combine band results into final result structure
    result = {}
    for band_result in band_results:
        result.update(band_result)
    
    # ===========================================
    # Apply JSON compression (same as freq_response_fulltrack)
    # ===========================================
    
    # For each band, find the minimum value and use it as origin
    # Round to 4 decimal places for stereo width precision
    for band_key in result.keys():
        values = result[band_key]["width_ratio"]["values"]
        if values:
            min_value = min(values)  # No NaN filtering - fail hard if NaN present
            # Subtract minimum from all values (origin compression) and round to 4 decimals
            result[band_key]["width_ratio"]["origin_value"] = round(min_value, 4)
            result[band_key]["width_ratio"]["values"] = [
                round(v - min_value, 4) for v in values  # No NaN handling - fail hard
            ]
        else:
            result[band_key]["width_ratio"]["values"] = []
    
    return {"result": result}