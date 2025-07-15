import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

def transient_rms(signal, frame_size):
    frame_energy = []
    for i in range(0, len(signal), frame_size):
        frame = signal[i:i+frame_size]
        if len(frame) == 0:
            continue
        rms = np.sqrt(np.mean(np.square(frame)))
        frame_energy.append(rms)
    return np.mean(frame_energy) if frame_energy else 0.0

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    low_hz = int(config.get("multiband::cutoff_low_freqHz", 2000))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))
    bands = int(config.get("multiband::bands", 4))
    frame_ms = int(config.get("sparkle::frame_ms", 20))
    sparkle_threshold = int(config.get("sparkle::min_frequency_hz", 2000))

    # Calculate total octaves for compensation
    total_octaves = np.log2(high_hz / low_hz)

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
            if data.ndim == 1:
                signal = data
            else:
                signal = np.mean(data, axis=1)

            frame_size = int(rate * frame_ms / 1000.0)

            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

                try:
                    # Check if this frequency band is below 2kHz
                    if f_high < sparkle_threshold:
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

                    output[range_key].append({
                        "chunk": chunk,
                        "sparkle": round(float(sparkle_value_compensated), 6)
                    })

                except Exception as e:
                    output[range_key].append({
                        "chunk": chunk,
                        "sparkle": None,
                        "error": str(e)
                    })

        except Exception as e:
            # Add error entries for all frequency ranges
            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                output[range_key].append({
                    "chunk": chunk,
                    "sparkle": None,
                    "error": str(e)
                })

    return {"result": output}