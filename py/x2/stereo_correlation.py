import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    low_hz = int(config.get("multiband::cutoff_low_freqHz", 2000))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))
    bands = int(config.get("multiband::bands", 6))

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
                        "correlation": None,
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
                    "correlation": None,
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

                # Simple correlation
                if np.std(left_band) == 0 or np.std(right_band) == 0:
                    correlation = 1.0 if np.allclose(left_band, right_band) else 0.0
                else:
                    correlation = np.corrcoef(left_band, right_band)[0, 1]

                output[range_key].append({
                    "chunk": chunk,
                    "correlation": round(float(correlation), 4) if not np.isnan(correlation) else None
                })

            except Exception as e:
                output[range_key].append({
                    "chunk": chunk,
                    "correlation": None,
                    "error": str(e)
                })

    return {"result": output}