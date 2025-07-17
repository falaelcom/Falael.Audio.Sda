def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   quantization_data = previous.get("quantization", {}).get("result", {})
   dynamics_full_spectrum_data = previous.get("dynamics_full_spectrum", {}).get("result", [])
   
   if not quantization_data:
       return {"error": "Missing quantization result."}
   
   # Initialize output
   output = {}
   
   # Create overall avg crest factor and std crest factor lookup by chunk name
   overall_crest_lookup = {}
   std_crest_lookup = {}
   for chunk_data in dynamics_full_spectrum_data:
       chunk_name = chunk_data.get("chunk")
       avg_crest_factor_db = chunk_data.get("avg_crest_factor_db")
       std_crest_factor_db = chunk_data.get("std_crest_factor_db")
       if chunk_name and avg_crest_factor_db is not None:
           overall_crest_lookup[chunk_name] = avg_crest_factor_db
       if chunk_name and std_crest_factor_db is not None:
           std_crest_lookup[chunk_name] = std_crest_factor_db
   
   # Iterate over original ordered keys to preserve band ordering
   for band in quantization_data.keys():
       output[band] = []
       
       quantization_band_data = quantization_data[band]
       
       for i in range(len(quantization_band_data)):
           quantization_chunk = quantization_band_data[i]
           
           chunk_name = quantization_chunk.get("chunk")
           
           try:
               # Extract values from dynamics
               
               # Overall avg crest factor (same for all bands per chunk)
               overall_avg_crest_factor_db = overall_crest_lookup.get(chunk_name)
               
               # Overall std crest factor (same for all bands per chunk)
               overall_std_crest_factor_db = std_crest_lookup.get(chunk_name)
               
               # Check for errors in source data
               error_messages = []
               if quantization_chunk.get("error"):
                   error_messages.append(f"quantization: {quantization_chunk['error']}")
               
               output[band].append({
                   "chunk": chunk_name,
                   "overall_avg_crest_factor_db": round(overall_avg_crest_factor_db, 2) if overall_avg_crest_factor_db is not None else None,
                   "overall_std_crest_factor_db": round(overall_std_crest_factor_db, 2) if overall_std_crest_factor_db is not None else None,
                   "error": "; ".join(error_messages) if error_messages else None
               })
               
           except Exception as e:
               output[band].append({
                   "chunk": chunk_name,
                   "overall_avg_crest_factor_db": None,
                   "overall_std_crest_factor_db": None,
                   "error": str(e)
               })
   
   return {"result": output}