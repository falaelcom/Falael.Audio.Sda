import os
import numpy as np
import soundfile as sf
from scipy import signal

# To get actual dB values:
# `actual_db = origin_value + relative_value`
# To get time:
# `time_ms = (origin_sample + i * interval_samples) * 1000 / sample_rate`

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    """
    Calculate track-relative frequency response using sliding windows.
    
    This creates a dense time series showing how energy in each frequency band
    changes relative to the track's average energy in that band.
    
    Two-pass algorithm:
    1. Calculate track-wide average energy per frequency band (baseline)
    2. Use sliding windows to show deviations from baseline over time
    """
    
    # Get configuration parameters
    window_samples = int(config.get("freq_response_fulltrack::window_samples", 4096))  # FFT window size
    hop_samples = int(config.get("freq_response_fulltrack::hop_samples", 2048))        # Step between windows
    low_hz = int(config.get("multiband::cutoff_low_freqHz", 100))                     # Lowest frequency to analyze
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))                 # Highest frequency to analyze
    bands = int(config.get("multiband::bands", 8))                                    # Number of frequency bands
    
    try:
        # Load the entire audio file
        data, sample_rate = sf.read(file_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # Convert stereo to mono by averaging channels
            
    except Exception as e:
        return {"error": f"Failed to load audio file: {str(e)}"}
    
    # Create logarithmically-spaced frequency bands
    # Why logarithmic? Human hearing perceives frequency ratios, not differences
    # (e.g., 100Hz to 200Hz sounds like the same "distance" as 1000Hz to 2000Hz)
    log_start = np.log10(low_hz)      # Convert to log scale
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)  # Create band boundaries
    
    # ===========================================
    # PASS 1: Calculate Track-Wide Energy Baseline Using Scipy STFT
    # ===========================================
    
    # Calculate overlap for scipy STFT
    # noverlap = window_samples - hop_samples
    noverlap = window_samples - hop_samples
    
    # Use scipy's optimized STFT (Short-Time Fourier Transform)
    # This is much faster than manual sliding window + FFT
    # Returns: frequencies, times, and complex STFT matrix
    frequencies, times, stft_matrix = signal.stft(
        data,
        fs=sample_rate,
        window='hann',           # Hanning window (same as np.hanning)
        nperseg=window_samples,  # Window size
        noverlap=noverlap        # Overlap between windows
    )
    
    # Get magnitude spectrum (ignore phase)
    # stft_matrix shape: (freq_bins, time_frames)
    magnitude_spectrum = np.abs(stft_matrix)
    
    # We'll collect energy measurements from across the entire track
    # to establish what "normal" energy looks like in each frequency band
    baseline_energies = {}
    for i in range(bands):
        baseline_energies[f"{int(log_edges[i])}Hz-{int(log_edges[i+1])}Hz"] = []
    
    # Process each time frame from the STFT
    for frame_idx in range(magnitude_spectrum.shape[1]):
        frame_magnitude = magnitude_spectrum[:, frame_idx]
        
        # Calculate energy in each frequency band
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i+1]
            band_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            
            # Find which frequency bins fall within this band
            bin_mask = (frequencies >= f_low) & (frequencies <= f_high)
            
            if np.any(bin_mask):
                # Sum up energy in all bins within this band
                # Energy = magnitude squared
                band_energy = np.sum(frame_magnitude[bin_mask] ** 2)
                
                # Normalize by bandwidth to get energy density (energy per Hz)
                # This makes narrow and wide bands comparable
                band_width = f_high - f_low
                energy_density = band_energy / band_width
                
                baseline_energies[band_key].append(energy_density)
    
    # Calculate average energy density for each band across the entire track
    # This becomes our "baseline" - what we consider normal energy for each band
    track_baselines = {}
    for band_key, energy_list in baseline_energies.items():
        if energy_list:
            track_baselines[band_key] = np.mean(energy_list)
        else:
            track_baselines[band_key] = 1e-12  # Tiny value to avoid division by zero
    
    # ===========================================
    # PASS 2: Generate Track-Relative Time Series
    # ===========================================
    
    # Initialize result structure
    result = {}
    for band_key in track_baselines.keys():
        result[band_key] = {
            "track_relative_energy_db": {
                "origin_value": 0.0,        # Will be set to minimum value for compression
                "origin_sample": 0,         # First sample position
                "interval_samples": hop_samples,  # Samples between each measurement
                "sample_rate": sample_rate, # For consumer time conversion
                "values": []                # Relative energy values
            }
        }
    
    # Process each time frame from the already-computed STFT
    for frame_idx in range(magnitude_spectrum.shape[1]):
        frame_magnitude = magnitude_spectrum[:, frame_idx]
        
        # Calculate energy for each band and compare to baseline
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i+1]
            band_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            
            bin_mask = (frequencies >= f_low) & (frequencies <= f_high)
            
            if np.any(bin_mask):
                # Calculate current energy density
                band_energy = np.sum(frame_magnitude[bin_mask] ** 2)
                band_width = f_high - f_low
                current_energy_density = band_energy / band_width
                
                # Convert to dB relative to track baseline
                # dB = 20 * log10(current / baseline)
                # Positive dB = higher than average energy
                # Negative dB = lower than average energy
                baseline = track_baselines[band_key]
                if current_energy_density > 0 and baseline > 0:
                    relative_db = 20 * np.log10(current_energy_density / baseline)
                else:
                    relative_db = -60.0  # Very low floor for silence
                
                result[band_key]["track_relative_energy_db"]["values"].append(relative_db)
            else:
                # No energy in this band
                result[band_key]["track_relative_energy_db"]["values"].append(-60.0)
    
    # ===========================================
    # PASS 3: Optimize JSON Size Using Origin Compression
    # ===========================================
    
    # For each band, find the minimum value and use it as origin
    # This way we store smaller relative values instead of large absolute values
    # Round to 1 decimal place to reduce JSON size significantly
    for band_key in result.keys():
        values = result[band_key]["track_relative_energy_db"]["values"]
        if values:
            min_value = min(values)
            # Subtract minimum from all values (origin compression) and round to 1 decimal
            result[band_key]["track_relative_energy_db"]["origin_value"] = round(min_value, 1)
            result[band_key]["track_relative_energy_db"]["values"] = [
                round(v - min_value, 1) for v in values
            ]
        else:
            result[band_key]["track_relative_energy_db"]["values"] = []
    
    return {"result": result}