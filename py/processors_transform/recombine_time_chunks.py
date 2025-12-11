ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import numpy as np
import soundfile as sf

import processors_transform.partition as partition

from zulu.fs_cache_utils import get_file_timestamp, get_file_timestamps, get_keys
from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:
    """
    Recombine processed audio time-chunks into a single full-track file.
    
    Args:
        session: Session data containing chunk information
        profile: Configuration profile
        internal_storage: Storage manager
        file_path: Original file path (for output naming)
        pipeline_options: Options dict containing chunks_source_processor_name
        
    Returns:
        Dict with processing results
    """
    
    chunks_source_processor_name = (pipeline_options or {}).get("chunks_source_processor_name", partition.PROCESSOR_NAME)
    
    assert (chunks_root := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["dir_name"])
    assert (chunk_list := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["file_names"])
    
    # Parameters for caching
    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_chunks_source_processor_name": chunks_source_processor_name,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
    })
    
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    
    if previous: 
        internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))
    
    original_basename = os.path.basename(file_path)
    out_path = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)
    os.makedirs(out_path, exist_ok=True)
    
    # Load and concatenate all chunks in order
    combined_audio = None
    sample_rate = None
    
    for i, chunk_filename in enumerate(chunk_list):
        chunk_path = os.path.join(chunks_root, chunk_filename)
        
        if not os.path.exists(chunk_path):
            raise FileNotFoundError(f"Chunk file not found: {chunk_path}")
        
        # Load chunk audio
        chunk_data, chunk_sample_rate = sf.read(chunk_path)
        
        # Initialize on first chunk
        if combined_audio is None:
            combined_audio = chunk_data
            sample_rate = chunk_sample_rate
            subtype = sf.info(chunk_path).subtype
        else:
            # Verify sample rate consistency
            if chunk_sample_rate != sample_rate:
                raise ValueError(f"Sample rate mismatch: expected {sample_rate}, got {chunk_sample_rate} in {chunk_filename}")
            
            # Concatenate audio data
            combined_audio = np.concatenate([combined_audio, chunk_data], axis=0)
    
    if combined_audio is None:
        raise RuntimeError("No audio data to recombine")
    
    # Generate output filename
    output_file_name = f"recombined.{original_basename}"
    output_path = os.path.join(out_path, output_file_name)
    
    # Save combined audio file
    sf.write(output_path, combined_audio, sample_rate, subtype = subtype) #, subtype='FLOAT') #, format='FLAC', subtype='PCM_24')
    
    # Get output root directory
    # dir_name = os.path.relpath(out_path, ".")  # was relatiove
    dir_name = os.path.abspath(out_path) # now is a full path
    
    data = {
        "params_version": new_params_version, 
        "params": params,
        "result": {
            "dir_name": dir_name,
            "file_name": output_file_name,
        }
    }
    
    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)
    
    return {
        "from_cache": False,
        "data": data
    }