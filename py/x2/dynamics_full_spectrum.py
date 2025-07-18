import os
import numpy as np
import soundfile as sf
from lib.chunk_parallel_process import chunk_parallel_process

def rms_dbfs(signal: np.ndarray) -> float:
    rms = np.sqrt(np.mean(signal ** 2))
    if rms == 0:
        return -np.inf
    return 20 * np.log10(rms)

def peak_dbfs(signal: np.ndarray) -> float:
    peak = np.max(np.abs(signal))
    if peak == 0:
        return -np.inf
    return 20 * np.log10(peak)

def process_single_chunk(chunk_path, chunk, frame_ms):
    try:
        data, rate = sf.read(chunk_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # Convert to mono
        
        frame_size = int(rate * frame_ms / 1000.0)
        
        # Calculate frame-by-frame metrics
        frame_peaks = []
        frame_rms = []
        
        for i in range(0, len(data), frame_size):
            frame = data[i:i+frame_size]
            if len(frame) == 0:
                continue
                
            frame_peak = np.max(np.abs(frame))
            frame_rms_val = np.sqrt(np.mean(frame ** 2))
            
            if frame_peak > 0:
                frame_peaks.append(frame_peak)
            if frame_rms_val > 0:
                frame_rms.append(frame_rms_val)
        
        # Overall chunk metrics
        chunk_peak_dbfs = peak_dbfs(data)
        chunk_rms_dbfs = rms_dbfs(data)
        
        # Crest factor (peak to RMS ratio)
        if chunk_rms_dbfs != -np.inf and chunk_peak_dbfs != -np.inf:
            crest_factor_db = chunk_peak_dbfs - chunk_rms_dbfs
        else:
            crest_factor_db = None
        
        # Dynamic range metrics from frame analysis
        if frame_peaks and frame_rms:
            # Calculate all metrics in one pass
            min_peak = np.min(frame_peaks)
            max_peak = np.max(frame_peaks)
            min_rms = np.min(frame_rms)
            max_rms = np.max(frame_rms)

            # Dynamic range calculations
            if min_peak > 1e-12:
                peak_dyn_range_db = 20 * np.log10(max_peak / min_peak)
            else:
                peak_dyn_range_db = min(120.0, 20 * np.log10(max_peak / 1e-12))

            if min_rms > 1e-12:
                rms_dyn_range_db = 20 * np.log10(max_rms / min_rms)
            else:
                rms_dyn_range_db = min(120.0, 20 * np.log10(max_rms / 1e-12))

            # Crest factor calculations
            frame_crest_factors_db = [20 * np.log10(peak / max(rms, 1e-12)) 
                                     for peak, rms in zip(frame_peaks, frame_rms)]
            avg_crest_factor_db = np.mean(frame_crest_factors_db) if frame_crest_factors_db else None
            std_crest_factor_db = np.std(frame_crest_factors_db) if len(frame_crest_factors_db) > 1 else None

        else:
            peak_dyn_range_db = None
            rms_dyn_range_db = None
            avg_crest_factor_db = None
            std_crest_factor_db = None

        return {
            "chunk": chunk,
            "peak_dbfs": round(chunk_peak_dbfs, 2) if chunk_peak_dbfs != -np.inf else None,
            "rms_dbfs": round(chunk_rms_dbfs, 2) if chunk_rms_dbfs != -np.inf else None,
            "crest_factor_db": round(crest_factor_db, 2) if crest_factor_db is not None else None,
            "peak_dyn_range_db": round(peak_dyn_range_db, 2) if peak_dyn_range_db is not None else None,
            "rms_dyn_range_db": round(rms_dyn_range_db, 2) if rms_dyn_range_db is not None else None,
            "avg_crest_factor_db": round(avg_crest_factor_db, 2) if avg_crest_factor_db is not None else None,
            "std_crest_factor_db": round(std_crest_factor_db, 2) if std_crest_factor_db is not None else None
        }

    except Exception as e:
        return {
            "chunk": chunk,
            "peak_dbfs": None,
            "rms_dbfs": None,
            "crest_factor_db": None,
            "peak_dyn_range_db": None,
            "rms_dyn_range_db": None,
            "avg_crest_factor_db": None,
            "std_crest_factor_db": None,
            "error": str(e)
        }

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['frame_ms'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    frame_ms = int(config.get("dynamics_full_spectrum::frame_ms", 100))
    max_workers = config.get("parallel::max_workers", None)
    
    # Create context object for callback
    context = {
        'frame_ms': frame_ms
    }

    # Process all chunks in parallel using threads
    results = chunk_parallel_process(_chunk_callback, chunk_list, out_path, context, max_workers, use_processes=False)

    return {"result": results}