import os
import numpy as np
import soundfile as sf

def calculate_sinad_for_chunk(chunk_path, config):
    """Calculate SINAD (Signal-to-Noise-And-Distortion) for a chunk"""
    try:
        data, rate = sf.read(chunk_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # Convert to mono
        
        # Configuration
        fft_size = int(config.get("sinad::fft_size", 4096))
        overlap = float(config.get("sinad::overlap", 0.5))
        noise_percentile = float(config.get("sinad::noise_percentile", 10))
        
        step_size = int(fft_size * (1 - overlap))
        
        # Collect SINAD measurements from all frames
        frame_sinads = []
        
        for i in range(0, len(data) - fft_size, step_size):
            frame = data[i:i+fft_size]
            windowed = frame * np.hanning(fft_size)
            fft_mag = np.abs(np.fft.rfft(windowed))
            
            # Calculate total signal energy
            total_energy = np.sum(fft_mag ** 2)
            
            if total_energy == 0:
                continue
            
            # Estimate noise floor energy (bottom percentile of spectrum)
            sorted_mags = np.sort(fft_mag)
            noise_floor_samples = int(len(sorted_mags) * noise_percentile / 100)
            noise_floor_samples = max(1, noise_floor_samples)  # At least 1 sample
            
            # Average magnitude of noise floor
            noise_floor_mag = np.mean(sorted_mags[:noise_floor_samples])
            
            # Estimate total noise energy across all bins
            # Assume noise floor applies to all frequency bins
            noise_energy = (noise_floor_mag ** 2) * len(fft_mag)
            
            # SINAD = Total Signal Energy / Noise Energy
            if noise_energy > 0:
                sinad_ratio = total_energy / noise_energy
                sinad_db = 10 * np.log10(sinad_ratio)
                frame_sinads.append(sinad_db)
        
        # Calculate average SINAD for the chunk
        if frame_sinads:
            avg_sinad_db = np.mean(frame_sinads)
            min_sinad_db = np.min(frame_sinads)
            max_sinad_db = np.max(frame_sinads)
            std_sinad_db = np.std(frame_sinads)
            
            return {
                "avg_sinad_db": round(avg_sinad_db, 2),
                "min_sinad_db": round(min_sinad_db, 2),
                "max_sinad_db": round(max_sinad_db, 2),
                "std_sinad_db": round(std_sinad_db, 2),
                "frames_analyzed": len(frame_sinads)
            }
        else:
            return {
                "avg_sinad_db": None,
                "min_sinad_db": None,
                "max_sinad_db": None,
                "std_sinad_db": None,
                "frames_analyzed": 0
            }
            
    except Exception as e:
        return {
            "avg_sinad_db": None,
            "min_sinad_db": None,
            "max_sinad_db": None,
            "std_sinad_db": None,
            "frames_analyzed": 0,
            "sinad_error": str(e)
        }

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    quantization_data = previous.get("quantization", {}).get("result", {})
    harmonics_data = previous.get("harmonics", {}).get("result", {})
    harmonics_full_spectrum_data = previous.get("harmonics_full_spectrum", {}).get("result", [])
    
    if not quantization_data:
        return {"error": "Missing quantization result."}
    
    if not harmonics_data:
        return {"error": "Missing harmonics result."}
    
    # Check if both sources have the same frequency bands
    quantization_bands = set(quantization_data.keys())
    harmonics_bands = set(harmonics_data.keys())
    
    if quantization_bands != harmonics_bands:
        return {"error": f"Band mismatch: quantization has {quantization_bands}, harmonics has {harmonics_bands}"}
    
    # Check if chunk counts match for each band
    for band in quantization_bands:
        quantization_chunks = len(quantization_data[band])
        harmonics_chunks = len(harmonics_data[band])
        
        if quantization_chunks != harmonics_chunks:
            return {"error": f"Chunk count mismatch in band {band}: quantization has {quantization_chunks}, harmonics has {harmonics_chunks}"}
        
        # Check if chunk names match
        quantization_chunk_names = [chunk.get("chunk") for chunk in quantization_data[band]]
        harmonics_chunk_names = [chunk.get("chunk") for chunk in harmonics_data[band]]
        
        if quantization_chunk_names != harmonics_chunk_names:
            return {"error": f"Chunk name mismatch in band {band}"}
    
    # Configuration
    flatness_db_floor = float(config.get("audio_quality::flatness_db_floor", 0.0))
    
    # Initialize output
    output = {}
    
    # Calculate SINAD once per chunk (will be same for all bands)
    chunk_sinad_cache = {}
    
    # Create overall spectral flatness lookup by chunk name
    spectral_flatness_ratio_lookup = {}
    for chunk_data in harmonics_full_spectrum_data:
        chunk_name = chunk_data.get("chunk")
        spectral_flatness_ratio_data = chunk_data.get("spectral_flatness_ratio")
        if chunk_name and spectral_flatness_ratio_data is not None:
            spectral_flatness_ratio_lookup[chunk_name] = spectral_flatness_ratio_data
    
    for band in quantization_bands:
        output[band] = []
        
        quantization_band_data = quantization_data[band]
        harmonics_band_data = harmonics_data[band]
        
        for i in range(len(quantization_band_data)):
            quantization_chunk = quantization_band_data[i]
            harmonics_chunk = harmonics_band_data[i]
            
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
                
                # 2. SINAD calculation (same for all bands per chunk)
                if chunk_name not in chunk_sinad_cache:
                    chunk_path = os.path.join(out_path, chunk_name)
                    chunk_sinad_cache[chunk_name] = calculate_sinad_for_chunk(chunk_path, config)
                
                sinad_results = chunk_sinad_cache[chunk_name]
                
                # 3. Overall spectral flatness (same for all bands per chunk)
                spectral_flatness_ratio = spectral_flatness_ratio_lookup.get(chunk_name)
                
                # Check for errors in source data
                error_messages = []
                if quantization_chunk.get("error"):
                    error_messages.append(f"quantization: {quantization_chunk['error']}")
                if harmonics_chunk.get("error"):
                    error_messages.append(f"harmonics: {harmonics_chunk['error']}")
                if sinad_results.get("sinad_error"):
                    error_messages.append(f"sinad: {sinad_results['sinad_error']}")
                
                # Combine results
                result = {
                    "chunk": chunk_name,
                    "quantization_efficiency": round(quantization_efficiency, 4) if quantization_efficiency is not None else None,
                    "spectral_flatness_ratio": round(spectral_flatness_ratio, 6) if spectral_flatness_ratio is not None else None,
                }
                
                # Add SINAD results (same for all bands)
                result.update({
                    "avg_sinad_db": sinad_results.get("avg_sinad_db"),
                    "min_sinad_db": sinad_results.get("min_sinad_db"),
                    "max_sinad_db": sinad_results.get("max_sinad_db"),
                    "std_sinad_db": sinad_results.get("std_sinad_db")
                })
                
                if error_messages:
                    result["error"] = "; ".join(error_messages)
                
                output[band].append(result)
                
            except Exception as e:
                output[band].append({
                    "chunk": chunk_name,
                    "quantization_efficiency": None,
                    "spectral_flatness_ratio": None,
                    "avg_sinad_db": None,
                    "min_sinad_db": None,
                    "max_sinad_db": None,
                    "std_sinad_db": None,
                    "error": str(e)
                })
    
    return {"result": output}