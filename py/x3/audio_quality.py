import os
import numpy as np
import soundfile as sf

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    quantization_data = previous.get("quantization", {}).get("result", {})
    harmonics_full_spectrum_data = previous.get("harmonics_full_spectrum", {}).get("result", [])
    
    if not quantization_data:
        return {"error": "Missing quantization result."}
    
    # Check if both sources have the same frequency bands
    quantization_bands = set(quantization_data.keys())
    
    # Initialize output
    output = {}
    
    # Create overall spectral flatness lookup by chunk name
    spectral_flatness_ratio_lookup = {}
    std_spectral_flatness_ratio_lookup = {}
    for chunk_data in harmonics_full_spectrum_data:
        chunk_name = chunk_data.get("chunk")
        spectral_flatness_ratio_data = chunk_data.get("overall_spectral_flatness_ratio")
        std_spectral_flatness_ratio_data = chunk_data.get("std_overall_spectral_flatness_ratio")
        if chunk_name and spectral_flatness_ratio_data is not None:
            spectral_flatness_ratio_lookup[chunk_name] = spectral_flatness_ratio_data
        if chunk_name and std_spectral_flatness_ratio_data is not None:
            std_spectral_flatness_ratio_lookup[chunk_name] = std_spectral_flatness_ratio_data
    
    for band in quantization_bands:
        output[band] = []
        
        quantization_band_data = quantization_data[band]
        
        for i in range(len(quantization_band_data)):
            quantization_chunk = quantization_band_data[i]
            
            chunk_name = quantization_chunk.get("chunk")
            
            try:
                # Extract values from quantization
                estimated_bits = quantization_chunk.get("estimated_bits")
                unique_levels = quantization_chunk.get("unique_levels")
                
                # Calculate consolidated audio quality metrics
                
                # 1. Quantization quality (combination of bits and levels)
                if estimated_bits is not None and unique_levels is not None:
                    # Ratio of actual levels to theoretical levels
                    theoretical_levels = 2 ** estimated_bits if estimated_bits > 0 else 1
                    quantization_efficiency = unique_levels / theoretical_levels if theoretical_levels > 0 else 0
                else:
                    quantization_efficiency = None
                
                # 2. Overall spectral flatness (same for all bands per chunk)
                overall_spectral_flatness_ratio = spectral_flatness_ratio_lookup.get(chunk_name)
                
                # 3. Standard deviation of spectral flatness (same for all bands per chunk)
                std_overall_spectral_flatness_ratio = std_spectral_flatness_ratio_lookup.get(chunk_name)
                
                # Check for errors in source data
                error_messages = []
                if quantization_chunk.get("error"):
                    error_messages.append(f"quantization: {quantization_chunk['error']}")
                
                # Combine results
                result = {
                    "chunk": chunk_name,
                    "quantization_efficiency": round(quantization_efficiency, 4) if quantization_efficiency is not None else None,
                    "overall_spectral_flatness_ratio": round(overall_spectral_flatness_ratio, 6) if overall_spectral_flatness_ratio is not None else None,
                    "std_overall_spectral_flatness_ratio": round(std_overall_spectral_flatness_ratio, 6) if std_overall_spectral_flatness_ratio is not None else None,
                }
                
                if error_messages:
                    result["error"] = "; ".join(error_messages)
                
                output[band].append(result)
                
            except Exception as e:
                output[band].append({
                    "chunk": chunk_name,
                    "quantization_efficiency": None,
                    "overall_spectral_flatness_ratio": None,
                    "std_overall_spectral_flatness_ratio": None,
                    "error": str(e)
                })
    
    return {"result": output}