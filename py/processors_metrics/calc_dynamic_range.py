ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_metrics.base_quantization as base_quantization
import processors_metrics.base_dynamics_fullspectrum as base_dynamics_fullspectrum



from zulu.fs_cache_utils import get_file_timestamps, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    assert (quantization_data := session_data[base_quantization.PROCESSOR_NAME]["result"])
    assert (quantization_params := session_data[base_quantization.PROCESSOR_NAME]["params"])
    assert (dynamics_full_spectrum_data := session_data[base_dynamics_fullspectrum.PROCESSOR_NAME]["result"])
    assert (dynamics_full_spectrum_params := session_data[base_dynamics_fullspectrum.PROCESSOR_NAME]["params"])
   
    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        base_quantization.PROCESSOR_NAME: quantization_params,
        base_dynamics_fullspectrum.PROCESSOR_NAME: dynamics_full_spectrum_params,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

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
           
            # Extract values from dynamics
               
            # Overall avg crest factor (same for all bands per chunk)
            overall_avg_crest_factor_db = overall_crest_lookup.get(chunk_name)
               
            # Overall std crest factor (same for all bands per chunk)
            overall_std_crest_factor_db = std_crest_lookup.get(chunk_name)
               
            output[band].append({
                "chunk": chunk_name,
                "overall_avg_crest_factor_db": round(overall_avg_crest_factor_db, 2) if overall_avg_crest_factor_db is not None else None,
                "overall_std_crest_factor_db": round(overall_std_crest_factor_db, 2) if overall_std_crest_factor_db is not None else None,
            })
   
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
