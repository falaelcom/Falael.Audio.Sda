import os
import numpy as np
import soundfile as sf

from lib.bandpass_filter import bandpass
from lib.chunk_parallel_process import chunk_parallel_process

def rms_dbfs(signal: np.ndarray) -> float:
   rms = np.sqrt(np.mean(signal ** 2))
   if rms == 0:
       return -np.inf
   return 20 * np.log10(rms)

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
                    "mid_rms": None,
                    "side_rms": None,
                    "width_ratio": None,
                    "presence": None,
                    "quality": None,
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
                "mid_rms": None,
                "side_rms": None,
                "width_ratio": None,
                "presence": None,
                "quality": None,
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

            # Calculate Mid/Side from bandpassed signals
            mid = 0.5 * (left_band + right_band)
            side = 0.5 * (left_band - right_band)

            mid_rms = rms_dbfs(mid)
            side_rms = rms_dbfs(side)

            if mid_rms == -np.inf:
                width_ratio = 0.0
            else:
                width_ratio = 10 ** (side_rms / 20) / 10 ** (mid_rms / 20)

            # Calculate derived metrics from width_ratio
            if width_ratio is not None and not np.isnan(width_ratio):
                # Presence: exponential approach to 1.0 (saturation_point = 2.0)
                presence = 1 - np.exp(-width_ratio * 2.0 / 2.0)
                
                # Quality: piecewise function
                if width_ratio < 0.85:        # Professional range - most healthy content
                    quality = 1.0
                elif width_ratio <= 1.0:      # Acceptable but getting wide
                    quality = 1.0 - (width_ratio - 0.85) / (1.0 - 0.85)  # [1.0 → 0.0]
                elif width_ratio <= 1.3:      # Problematic territory
                    quality = -0.7 * (width_ratio - 1.0) / (1.3 - 1.0)   # [0.0 → -0.7]
                else:                         # Severely problematic
                    quality = -1.0
            else:
                presence = None
                quality = None

            result[range_key] = {
                "chunk": chunk,
                "mid_rms": round(mid_rms, 2) if mid_rms != -np.inf else None,
                "side_rms": round(side_rms, 2) if side_rms != -np.inf else None,
                "width_ratio": round(float(width_ratio), 4) if not np.isnan(width_ratio) else None,
                "presence": round(float(presence), 4) if presence is not None else None,
                "quality": round(float(quality), 4) if quality is not None else None
            }

        except Exception as e:
            result[range_key] = {
                "chunk": chunk,
                "mid_rms": None,
                "side_rms": None,
                "width_ratio": None,
                "presence": None,
                "quality": None,
                "error": str(e)
            }

    return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['log_edges'], ctx['bands'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   chunk_list = previous.get("split", {}).get("chunks", [])
   if not chunk_list:
       return {"error": "Missing or empty split result."}

   low_hz = int(config.get("multiband::cutoff_low_freqHz", 20))
   high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
   bands = int(config.get("multiband::bands", 10))
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