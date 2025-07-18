import os
import numpy as np
import soundfile as sf
from scipy import signal

from lib.bandpass_filter import bandpass
from lib.chunk_parallel_process import chunk_parallel_process

def calculate_phase_coherence(left_band, right_band, fft_size=256, overlap=0.75):
    """Calculate true phase coherence between two signals using STFT"""
    signal_length = len(left_band)
    
    # If signal is shorter than FFT size, return neutral coherence value
    if signal_length < fft_size:
        return 0.5  # Neutral coherence when phase analysis not possible
    
    # Calculate noverlap for scipy.signal.stft
    noverlap = int(fft_size * overlap)
    
    # Compute STFT for both channels
    f_left, t_left, Zxx_left = signal.stft(
        left_band, 
        fs=1.0,  # Normalized frequency since we don't need actual frequencies
        window='hann', 
        nperseg=fft_size, 
        noverlap=noverlap
    )
    
    f_right, t_right, Zxx_right = signal.stft(
        right_band, 
        fs=1.0, 
        window='hann', 
        nperseg=fft_size, 
        noverlap=noverlap
    )
    
    # Get number of time frames
    n_frames = Zxx_left.shape[1]
    
    if n_frames == 0:
        return None
    
    phase_coherence_values = []
    
    # Process each time frame
    for frame_idx in range(n_frames):
        left_fft = Zxx_left[:, frame_idx]
        right_fft = Zxx_right[:, frame_idx]
        
        # Extract phases
        phase_left = np.angle(left_fft)
        phase_right = np.angle(right_fft)
        
        # Calculate phase difference
        phase_diff = phase_left - phase_right
        
        # Wrap phase difference to [-π, π]
        phase_diff = np.angle(np.exp(1j * phase_diff))
        
        # Get magnitudes
        left_mag = np.abs(left_fft)
        right_mag = np.abs(right_fft)

        # Combine minimal threshold with weighting
        min_threshold = 1e-10  # Only exclude truly zero/NaN bins
        valid_bins = (left_mag > min_threshold) & (right_mag > min_threshold)

        if np.any(valid_bins):
            # Weight by energy within valid bins
            valid_left_mag = left_mag[valid_bins]
            valid_right_mag = right_mag[valid_bins]
            valid_phase_diff = phase_diff[valid_bins]
    
            weights = (valid_left_mag**2 + valid_right_mag**2)
            weights = weights / np.sum(weights)  # Normalize to sum to 1
    
            # Fixed phase coherence (-1 to +1 range)
            frame_coherence = np.average(np.cos(valid_phase_diff), weights=weights)
            phase_coherence_values.append(frame_coherence)
    
    if phase_coherence_values:
        final_coherence = np.mean(phase_coherence_values)
        return final_coherence
    else:
        return None

def process_single_chunk(chunk_path, chunk, log_edges, bands, fft_size, overlap):
    try:
        data, rate = sf.read(chunk_path)
        if data.ndim != 2 or data.shape[1] != 2:
            # Add error entries for all frequency ranges
            result = {}
            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                result[range_key] = {
                    "chunk": chunk,
                    "coherence": None,
                    "error": "Not stereo"
                }
            return result

        left = data[:, 0]
        right = data[:, 1]
        
    except Exception as e:
        # Add error entries for all frequency ranges
        result = {}
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i + 1]
            range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            result[range_key] = {
                "chunk": chunk,
                "coherence": None,
                "error": str(e)
            }
        return result

    # Process each frequency band
    result = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

        try:
            # Bandpass filter for this frequency range
            left_band = bandpass(left, rate, f_low, f_high)
            right_band = bandpass(right, rate, f_low, f_high)

            # Calculate true phase coherence
            coherence = calculate_phase_coherence(left_band, right_band, fft_size, overlap)

            result[range_key] = {
                "chunk": chunk,
                "coherence": round(float(coherence), 4) if coherence is not None else None
            }

        except Exception as e:
            result[range_key] = {
                "chunk": chunk,
                "coherence": None,
                "error": str(e)
            }

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['log_edges'], ctx['bands'], 
                               ctx['fft_size'], ctx['overlap'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    low_hz = int(config.get("multiband::cutoff_low_freqHz", 20))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
    bands = int(config.get("multiband::bands", 10))
    fft_size = int(config.get("stereo_phase::fft_size", 256))
    overlap = float(config.get("stereo_phase::overlap", 0.75))
    max_workers = config.get("parallel::max_workers", None)

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Create context object for callback
    context = {
        'log_edges': log_edges,
        'bands': bands,
        'fft_size': fft_size,
        'overlap': overlap
    }

    # Process all chunks in parallel using processes
    chunk_results = chunk_parallel_process(_chunk_callback, chunk_list, out_path, context, max_workers, use_processes=True)

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

    return {"result": output}