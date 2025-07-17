import os
import numpy as np
import soundfile as sf
import time
from scipy import signal

from .lib.bandpass_filter import bandpass

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

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    low_hz = int(config.get("multiband::cutoff_low_freqHz", 20))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
    bands = int(config.get("multiband::bands", 10))
    fft_size = int(config.get("stereo_phase::fft_size", 256))
    overlap = float(config.get("stereo_phase::overlap", 0.75))

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Initialize output grouped by frequency ranges
    output = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
        output[range_key] = []

    # Progress tracking
    total_operations = len(chunk_list) * bands
    completed_operations = 0
    start_time = time.time()
    
    # Enable progress printing for smaller FFT sizes that need more operations
    enable_progress = fft_size < 1024
    
    if enable_progress:
        print(f"    Processing {len(chunk_list)} chunks across {bands} frequency bands." f" Total operations: {total_operations}")

    for chunk_idx, chunk in enumerate(chunk_list):
        chunk_path = os.path.join(out_path, chunk)
        
        # Chunk-level progress
        chunk_start_time = time.time()
        if enable_progress:
            print(f"    Chunk {chunk_idx + 1}/{len(chunk_list)}: {chunk}")
        
        try:
            data, rate = sf.read(chunk_path)
            if data.ndim != 2 or data.shape[1] != 2:
                # Add error entries for all frequency ranges
                for i in range(bands):
                    f_low = log_edges[i]
                    f_high = log_edges[i + 1]
                    range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                    output[range_key].append({
                        "chunk": chunk,
                        "coherence": None,
                        "error": "Not stereo"
                    })
                    completed_operations += 1
                
                # Progress update for failed chunk
                elapsed_time = time.time() - start_time
                percent_complete = (completed_operations / total_operations) * 100
                if completed_operations > 0 and enable_progress:
                    eta_seconds = (elapsed_time / completed_operations) * (total_operations - completed_operations)
                    eta_minutes = eta_seconds / 60
                    print(f"      ERROR: Not stereo - Progress: {percent_complete:.1f}% | ETA: {eta_minutes:.1f}m")
                continue

            left = data[:, 0]
            right = data[:, 1]
            
        except Exception as e:
            # Add error entries for all frequency ranges
            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                output[range_key].append({
                    "chunk": chunk,
                    "coherence": None,
                    "error": str(e)
                })
                completed_operations += 1
                
            # Progress update for failed chunk
            elapsed_time = time.time() - start_time
            percent_complete = (completed_operations / total_operations) * 100
            if completed_operations > 0 and enable_progress:
                eta_seconds = (elapsed_time / completed_operations) * (total_operations - completed_operations)
                eta_minutes = eta_seconds / 60
                print(f"      ERROR: {str(e)} - Progress: {percent_complete:.1f}% | ETA: {eta_minutes:.1f}m")
            continue

        # Process each frequency band
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i + 1]
            range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

            # Show what we're about to process
            if enable_progress:
                print(f"      Band {i+1}/{bands}: {range_key}...", end=" ", flush=True)
            band_start_time = time.time()

            try:
                # Bandpass filter for this frequency range
                left_band = bandpass(left, rate, f_low, f_high)
                right_band = bandpass(right, rate, f_low, f_high)

                # Calculate true phase coherence
                coherence = calculate_phase_coherence(left_band, right_band, fft_size, overlap)

                output[range_key].append({
                    "chunk": chunk,
                    "coherence": round(float(coherence), 4) if coherence is not None else None
                })

            except Exception as e:
                output[range_key].append({
                    "chunk": chunk,
                    "coherence": None,
                    "error": str(e)
                })
                if enable_progress:
                    print(f"ERROR: {str(e)}", end=" ", flush=True)

            # Show band completion time
            band_elapsed = time.time() - band_start_time
            if enable_progress:
                print(f"done")

            # Update progress after each band
            completed_operations += 1
            
            # Print overall progress every 5 operations or for last operation
            if (completed_operations % 5 == 0 or completed_operations == total_operations) and enable_progress:
                elapsed_time = time.time() - start_time
                percent_complete = (completed_operations / total_operations) * 100
                
                if completed_operations > 0:
                    eta_seconds = (elapsed_time / completed_operations) * (total_operations - completed_operations)
                    eta_minutes = eta_seconds / 60
                    ops_per_sec = completed_operations / elapsed_time
                    
                    print(f"        >>> Overall Progress: {percent_complete:.1f}% | "
                          f"ETA: {eta_minutes:.1f}m | Speed: {ops_per_sec:.1f} ops/sec")
        
        # Chunk completion summary
        chunk_elapsed = time.time() - chunk_start_time
        if enable_progress:
            print(f"      Chunk completed in {chunk_elapsed:.1f}s")

    return {"result": output}