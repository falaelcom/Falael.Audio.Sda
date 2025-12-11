ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_metrics.base_stereo_width as base_stereo_width
import processors_metrics.base_stereo_phase as base_stereo_phase
import processors_metrics.base_stereo_correlation as base_stereo_correlation



from zulu.fs_cache_utils import get_file_timestamps, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    assert (stereo_width_data := session_data[base_stereo_width.PROCESSOR_NAME]["result"])
    assert (stereo_width_params := session_data[base_stereo_width.PROCESSOR_NAME]["params"])
    assert (stereo_phase_data := session_data[base_stereo_phase.PROCESSOR_NAME]["result"])
    assert (stereo_phase_params := session_data[base_stereo_phase.PROCESSOR_NAME]["params"])
    assert (stereo_correlation_data := session_data[base_stereo_correlation.PROCESSOR_NAME]["result"])
    assert (stereo_correlation_params := session_data[base_stereo_correlation.PROCESSOR_NAME]["params"])

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        base_stereo_width.PROCESSOR_NAME: stereo_width_params,
        base_stereo_phase.PROCESSOR_NAME: stereo_phase_params,
        base_stereo_correlation.PROCESSOR_NAME: stereo_correlation_params,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    # Get frequency bands
    stereo_width_bands = set(stereo_width_data.keys())
    
    # Initialize output
    output = {}
    
    # Create lookup tables for phase and correlation data by chunk name
    phase_lookup = {}
    correlation_lookup = {}
    
    for band in stereo_width_bands:
        phase_lookup[band] = {}
        correlation_lookup[band] = {}
        
        # Build phase lookup
        if band in stereo_phase_data:
            for chunk_data in stereo_phase_data[band]:
                chunk_name = chunk_data.get("chunk")
                coherence = chunk_data.get("coherence")
                if chunk_name and coherence is not None:
                    phase_lookup[band][chunk_name] = coherence
        
        # Build correlation lookup
        if band in stereo_correlation_data:
            for chunk_data in stereo_correlation_data[band]:
                chunk_name = chunk_data.get("chunk")
                correlation = chunk_data.get("correlation")
                if chunk_name and correlation is not None:
                    correlation_lookup[band][chunk_name] = correlation
    
    for band in stereo_width_bands:
        output[band] = []
        
        stereo_width_band_data = stereo_width_data[band]
        
        previous_width_ratio = None
        previous_phase_coherence = None
        previous_correlation = None
        
        for i, chunk_data in enumerate(stereo_width_band_data):
            chunk_name = chunk_data.get("chunk")
            current_width_ratio = chunk_data.get("width_ratio")
            current_phase_coherence = phase_lookup[band].get(chunk_name)
            current_correlation = correlation_lookup[band].get(chunk_name)
            
            # Calculate width deltas
            if i == 0 or previous_width_ratio is None or current_width_ratio is None:
                width_delta_abs = 0.0
                width_delta_rel = 0.0
            else:
                width_delta_abs = current_width_ratio - previous_width_ratio
                if previous_width_ratio != 0:
                    width_delta_rel = width_delta_abs / previous_width_ratio
                else:
                    width_delta_rel = 0.0
            
            # Calculate phase deltas
            if i == 0 or previous_phase_coherence is None or current_phase_coherence is None:
                phase_delta_abs = 0.0
                phase_delta_rel = 0.0
            else:
                phase_delta_abs = current_phase_coherence - previous_phase_coherence
                if previous_phase_coherence != 0:
                    phase_delta_rel = phase_delta_abs / previous_phase_coherence
                else:
                    phase_delta_rel = 0.0
            
            # Calculate correlation deltas
            if i == 0 or previous_correlation is None or current_correlation is None:
                correlation_delta_abs = 0.0
                correlation_delta_rel = 0.0
            else:
                correlation_delta_abs = current_correlation - previous_correlation
                if previous_correlation != 0:
                    correlation_delta_rel = correlation_delta_abs / previous_correlation
                else:
                    correlation_delta_rel = 0.0
            
            # Combine results
            result = {
                "chunk": chunk_name,
                "width_delta_abs": round(width_delta_abs, 4) if width_delta_abs is not None else None,
                "width_delta_rel": round(width_delta_rel, 4) if width_delta_rel is not None else None,
                "phase_delta_abs": round(phase_delta_abs, 4) if phase_delta_abs is not None else None,
                "phase_delta_rel": round(phase_delta_rel, 4) if phase_delta_rel is not None else None,
                "correlation_delta_abs": round(correlation_delta_abs, 4) if correlation_delta_abs is not None else None,
                "correlation_delta_rel": round(correlation_delta_rel, 4) if correlation_delta_rel is not None else None,
            }
                
            output[band].append(result)
            
            # Update previous values for next iteration
            previous_width_ratio = current_width_ratio
            previous_phase_coherence = current_phase_coherence
            previous_correlation = current_correlation
    
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