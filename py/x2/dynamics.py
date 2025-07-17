import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

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

def analyze_band_dynamics(band_signal, frame_ms, rate, chunk, range_key):
   """Analyze dynamics for a single frequency band"""
   try:
       frame_size = int(rate * frame_ms / 1000.0)
       
       # Calculate frame-by-frame metrics
       frame_peaks = []
       frame_rms = []
       
       for i in range(0, len(band_signal), frame_size):
           frame = band_signal[i:i+frame_size]
           if len(frame) == 0:
               continue
               
           frame_peak = np.max(np.abs(frame))
           frame_rms_val = np.sqrt(np.mean(frame ** 2))
           
           if frame_peak > 0:
               frame_peaks.append(frame_peak)
           if frame_rms_val > 0:
               frame_rms.append(frame_rms_val)
       
       # Overall band metrics
       band_peak_dbfs = peak_dbfs(band_signal)
       band_rms_dbfs = rms_dbfs(band_signal)
       
       # Crest factor (peak to RMS ratio)
       if band_rms_dbfs != -np.inf and band_peak_dbfs != -np.inf:
           crest_factor_db = band_peak_dbfs - band_rms_dbfs
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
           "peak_dbfs": round(band_peak_dbfs, 2) if band_peak_dbfs != -np.inf else None,
           "rms_dbfs": round(band_rms_dbfs, 2) if band_rms_dbfs != -np.inf else None,
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

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   chunk_list = previous.get("split", {}).get("chunks", [])
   if not chunk_list:
       return {"error": "Missing or empty split result."}

   # Get configuration
   frame_ms = int(config.get("dynamics::frame_ms", 100))
   low_hz = int(config.get("multiband::cutoff_low_freqHz", 200))
   high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
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
                   "peak_dbfs": None,
                   "rms_dbfs": None,
                   "crest_factor_db": None,
                   "peak_dyn_range_db": None,
                   "rms_dyn_range_db": None,
                   "avg_crest_factor_db": None,
                   "std_crest_factor_db": None,
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
               
               # Analyze dynamics for this band
               band_result = analyze_band_dynamics(band_signal, frame_ms, rate, chunk, range_key)
               output[range_key].append(band_result)

           except Exception as e:
               output[range_key].append({
                   "chunk": chunk,
                   "peak_dbfs": None,
                   "rms_dbfs": None,
                   "crest_factor_db": None,
                   "peak_dyn_range_db": None,
                   "rms_dyn_range_db": None,
                   "avg_crest_factor_db": None,
                   "std_crest_factor_db": None,
                   "error": str(e)
               })

   return {"result": output}