import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

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
    try:
        # Calculate spectral centroid fraction (brightness within band)
        centroid_fraction = normalized_spectral_centroid(band_signal, fft_size, step_size, sample_rate, f_low, f_high)
        
        # Calculate spectral rolloff fraction (energy distribution within band)
        rolloff_fraction = normalized_spectral_rolloff(band_signal, fft_size, step_size, sample_rate, f_low, f_high)
        
        return {
            "chunk": chunk,
            "spectral_centroid_fraction": round(centroid_fraction, 4) if centroid_fraction is not None else None,
            "spectral_rolloff_fraction": round(rolloff_fraction, 4) if rolloff_fraction is not None else None
        }

    except Exception as e:
        return {
            "chunk": chunk,
            "spectral_centroid_fraction": None,
            "spectral_rolloff_fraction": None,
            "error": str(e)
        }

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    # Get configuration
    fft_size = int(config.get("harmonics::fft_size", 4096))
    step_size = int(config.get("harmonics::hop_size", 2048))
    low_hz = int(config.get("multiband::cutoff_low_freqHz", 20))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
    bands = int(config.get("multiband::bands", 10))

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
            if data.ndim > 1:
                data = np.mean(data, axis=1)  # Convert to mono
                
        except Exception as e:
            # Add error entries for all frequency ranges
            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                output[range_key].append({
                    "chunk": chunk,
                    "spectral_centroid_fraction": None,
                    "spectral_rolloff_fraction": None,
                    "error": str(e)
                })
            continue

        # Process each frequency band
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i + 1]
            range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

            try:
                # Bandpass filter for this frequency range
                band_signal = bandpass(data, rate, f_low, f_high)
                
                # Analyze spectral characteristics for this band
                band_result = analyze_band_harmonics(band_signal, fft_size, step_size, rate, f_low, f_high, chunk, range_key)
                output[range_key].append(band_result)

            except Exception as e:
                output[range_key].append({
                    "chunk": chunk,
                    "spectral_centroid_fraction": None,
                    "spectral_rolloff_fraction": None,
                    "error": str(e)
                })

    return {"result": output}