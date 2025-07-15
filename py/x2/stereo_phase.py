import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

def calculate_phase_coherence(left_band, right_band, fft_size=256, overlap=0.75):
    """Calculate true phase coherence between two signals using FFT phase analysis"""
    signal_length = len(left_band)
    
    # If signal is shorter than FFT size, return neutral coherence value
    if signal_length < fft_size:
        return 0.5  # Neutral coherence when phase analysis not possible
    
    step_size = int(fft_size * (1 - overlap))
    phase_coherence_values = []
    
    for i in range(0, len(left_band) - fft_size, step_size):
        left_frame = left_band[i:i+fft_size]
        right_frame = right_band[i:i+fft_size]
        
        # Apply window
        window = np.hanning(fft_size)
        left_windowed = left_frame * window
        right_windowed = right_frame * window
        
        # FFT to get complex spectra
        left_fft = np.fft.fft(left_windowed)
        right_fft = np.fft.fft(right_windowed)
        
        # Extract phases
        phase_left = np.angle(left_fft)
        phase_right = np.angle(right_fft)
        
        # Calculate phase difference
        phase_diff = phase_left - phase_right
        
        # Wrap phase difference to [-π, π]
        phase_diff = np.angle(np.exp(1j * phase_diff))
        
        # Only use bins with significant energy to avoid noise-dominated phase
        left_mag = np.abs(left_fft)
        right_mag = np.abs(right_fft)
        energy_threshold = 0.01 * np.max(np.maximum(left_mag, right_mag))
        valid_bins = (left_mag > energy_threshold) & (right_mag > energy_threshold)
        
        if np.any(valid_bins):
            # Phase coherence: mean of |cos(phase_difference)|
            # 1.0 = perfect phase lock, 0.0 = random phases
            frame_coherence = np.mean(np.abs(np.cos(phase_diff[valid_bins])))
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

    for chunk in chunk_list:
        chunk_path = os.path.join(out_path, chunk)
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
            continue

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

    return {"result": output}