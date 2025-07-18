import os
import numpy as np
import soundfile as sf

from lib.bandpass_filter import bandpass
from lib.chunk_parallel_process import chunk_parallel_process

def process_single_chunk(chunk_path, chunk, log_edges, bands):
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
                    "correlation": None,
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
                "correlation": None,
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

            # Simple correlation
            if np.std(left_band) == 0 or np.std(right_band) == 0:
                correlation = 1.0 if np.allclose(left_band, right_band) else 0.0
            else:
                correlation = np.corrcoef(left_band, right_band)[0, 1]

            result[range_key] = {
                "chunk": chunk,
                "correlation": round(float(correlation), 4) if not np.isnan(correlation) else None
            }

        except Exception as e:
            result[range_key] = {
                "chunk": chunk,
                "correlation": None,
                "error": str(e)
            }

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['log_edges'], ctx['bands'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    low_hz = int(config.get("multiband::cutoff_low_freqHz", 2000))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))
    bands = int(config.get("multiband::bands", 6))
    max_workers = config.get("parallel::max_workers", None)

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Create context object for callback
    context = {
        'log_edges': log_edges,
        'bands': bands
    }

    # Process all chunks in parallel using processes
    chunk_results = chunk_parallel_process(_chunk_callback, chunk_list, out_path, context, max_workers, use_processes=False)

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