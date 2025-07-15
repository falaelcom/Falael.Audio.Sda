import os
import numpy as np

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   dynamics_data = previous.get("dynamics", {}).get("result", {})
   quantization_data = previous.get("quantization", {}).get("result", {})
   dynamics_full_spectrum_data = previous.get("dynamics_full_spectrum", {}).get("result", [])
   
   if not dynamics_data:
       return {"error": "Missing dynamics result."}
   
   if not quantization_data:
       return {"error": "Missing quantization result."}
   
   # Check if both sources have the same frequency bands
   dynamics_bands = set(dynamics_data.keys())
   quantization_bands = set(quantization_data.keys())
   
   if dynamics_bands != quantization_bands:
       return {"error": f"Band mismatch: dynamics has {dynamics_bands}, quantization has {quantization_bands}"}
   
   # Check if chunk counts match for each band
   for band in dynamics_bands:
       dynamics_chunks = len(dynamics_data[band])
       quantization_chunks = len(quantization_data[band])
       
       if dynamics_chunks != quantization_chunks:
           return {"error": f"Chunk count mismatch in band {band}: dynamics has {dynamics_chunks}, quantization has {quantization_chunks}"}
       
       # Check if chunk names match
       dynamics_chunk_names = [chunk.get("chunk") for chunk in dynamics_data[band]]
       quantization_chunk_names = [chunk.get("chunk") for chunk in quantization_data[band]]
       
       if dynamics_chunk_names != quantization_chunk_names:
           return {"error": f"Chunk name mismatch in band {band}"}
   
   # Configuration
   noise_floor_fallback_db = float(config.get("dynamic_range::noise_floor_fallback_db", -96.0))
   
   # Initialize output
   output = {}
   
   # Create overall avg crest factor lookup by chunk name
   overall_crest_lookup = {}
   for chunk_data in dynamics_full_spectrum_data:
       chunk_name = chunk_data.get("chunk")
       avg_crest_factor_db = chunk_data.get("avg_crest_factor_db")
       if chunk_name and avg_crest_factor_db is not None:
           overall_crest_lookup[chunk_name] = avg_crest_factor_db
   
   # Iterate over original ordered keys to preserve band ordering
   for band in dynamics_data.keys():
       output[band] = []
       
       dynamics_band_data = dynamics_data[band]
       quantization_band_data = quantization_data[band]
       
       for i in range(len(dynamics_band_data)):
           dynamics_chunk = dynamics_band_data[i]
           quantization_chunk = quantization_band_data[i]
           
           chunk_name = dynamics_chunk.get("chunk")
           
           try:
               # Extract values from dynamics
               peak_dbfs = dynamics_chunk.get("peak_dbfs")
               rms_dbfs = dynamics_chunk.get("rms_dbfs")
               crest_factor_db = dynamics_chunk.get("crest_factor_db")
               
               # Extract values from quantization
               quantization_dynamic_range_db = quantization_chunk.get("dynamic_range_db")
               noise_floor_db = quantization_chunk.get("avg_noise_floor_db")
               estimated_bits = quantization_chunk.get("estimated_bits")
               
               # Calculate consolidated dynamic range metrics
               
               # 1. Peak-to-noise ratio (dynamics peak - quantization noise floor)
               if peak_dbfs is not None and noise_floor_db is not None:
                   peak_to_noise_ratio_db = peak_dbfs - noise_floor_db
               elif peak_dbfs is not None:
                   # Fallback to estimated noise floor
                   peak_to_noise_ratio_db = peak_dbfs - noise_floor_fallback_db
               else:
                   peak_to_noise_ratio_db = None
               
               # 2. Signal-to-noise ratio (RMS - noise floor)
               if rms_dbfs is not None and noise_floor_db is not None:
                   signal_to_noise_ratio_db = rms_dbfs - noise_floor_db
               elif rms_dbfs is not None:
                   # Fallback to estimated noise floor
                   signal_to_noise_ratio_db = rms_dbfs - noise_floor_fallback_db
               else:
                   signal_to_noise_ratio_db = None
               
               # 3. Overall avg crest factor (same for all bands per chunk)
               overall_avg_crest_factor_db = overall_crest_lookup.get(chunk_name)
               
               # Check for errors in source data
               error_messages = []
               if dynamics_chunk.get("error"):
                   error_messages.append(f"dynamics: {dynamics_chunk['error']}")
               if quantization_chunk.get("error"):
                   error_messages.append(f"quantization: {quantization_chunk['error']}")
               
               output[band].append({
                   "chunk": chunk_name,
                   "peak_to_noise_ratio_db": round(peak_to_noise_ratio_db, 2) if peak_to_noise_ratio_db is not None else None,
                   "signal_to_noise_ratio_db": round(signal_to_noise_ratio_db, 2) if signal_to_noise_ratio_db is not None else None,
                   "overall_avg_crest_factor_db": round(overall_avg_crest_factor_db, 2) if overall_avg_crest_factor_db is not None else None,
                   "error": "; ".join(error_messages) if error_messages else None
               })
               
           except Exception as e:
               output[band].append({
                   "chunk": chunk_name,
                   "peak_to_noise_ratio_db": None,
                   "signal_to_noise_ratio_db": None,
                   "overall_avg_crest_factor_db": None,
                   "error": str(e)
               })
   
   return {"result": output}