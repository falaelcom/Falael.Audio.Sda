ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_metrics.base_quantization as base_quantization
import processors_metrics.base_harmonics_fullspectrum as base_harmonics_fullspectrum



from zulu.fs_cache_utils import get_file_timestamps, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    assert (quantization_data := session_data[base_quantization.PROCESSOR_NAME]["result"])
    assert (quantization_params := session_data[base_quantization.PROCESSOR_NAME]["params"])
    assert (harmonics_full_spectrum_data := session_data[base_harmonics_fullspectrum.PROCESSOR_NAME]["result"])
    assert (harmonics_full_spectrum_params := session_data[base_harmonics_fullspectrum.PROCESSOR_NAME]["params"])

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        base_quantization.PROCESSOR_NAME: quantization_params,
        base_harmonics_fullspectrum.PROCESSOR_NAME: harmonics_full_spectrum_params,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

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
            
            # Extract values from base_quantization
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
                
            # Combine results
            result = {
                "chunk": chunk_name,
                "quantization_efficiency": round(quantization_efficiency, 4) if quantization_efficiency is not None else None,
                "overall_spectral_flatness_ratio": round(overall_spectral_flatness_ratio, 6) if overall_spectral_flatness_ratio is not None else None,
                "std_overall_spectral_flatness_ratio": round(std_overall_spectral_flatness_ratio, 6) if std_overall_spectral_flatness_ratio is not None else None,
            }
                
            output[band].append(result)
    
   
    data = {
        "params_version": new_params_version, 
        "params": params, 
        "result": output
    }
    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }
