import os
import numpy as np
import soundfile as sf
from typing import List

# Import subprocessors
from processors_transform.zulu.transform_degrade_async_subprocessor_reverb import ReverbSubprocessor
from processors_transform.zulu.transform_degrade_async_subprocessor_signal_noise import SignalNoiseSubprocessor

def process_chunk_callback(item_index: int, chunk_obj: dict, ctx: dict):
    """
    Process a single chunk object and handle re-enqueuing for cascading.
    
    Args:
        item_index: Index of this item in the processing sequence
        chunk_obj: Chunk object with all necessary information
        ctx: Context dictionary with processing parameters
        
    Returns:
        None if processing complete, or dict with 'reenqueue_item' for re-enqueuing
    """
    
    chunk_index = chunk_obj['chunk_index']
    chunk_filename = chunk_obj['chunk_filename']
    chunk_root = chunk_obj['chunk_root']
    iteration_count = chunk_obj['iteration_count']
    is_first_processing = chunk_obj.get('is_first_processing', False)
    
    # Construct chunk path from chunk object
    chunk_path = os.path.join(chunk_root, chunk_filename)
    
    # Load chunk audio
    subtype = sf.info(chunk_path).subtype
    chunk_data, sample_rate = sf.read(chunk_path)
    if chunk_data.ndim != 2 or chunk_data.shape[1] != 2:
        raise ValueError(f"Chunk {chunk_filename} must be stereo")
    
    # Apply single degradation iteration
    processed_data = apply_degradation_to_chunk_single(
        chunk_data,
        sample_rate,
        ctx
    )
    
    # Save processed chunk
    if is_first_processing:
        processed_filename_prefix = ctx['processed_filename_prefix']
        processed_chunk_filename = f"{processed_filename_prefix}{chunk_filename}"
    else:
        # Keep the same filename for subsequent iterations
        processed_chunk_filename = chunk_filename
    
    # Get output directory
    out_root = ctx['internal_storage'].get_root_dir(
        ctx['processor_name'], 
        ctx['algo_version'], 
        ctx['params_version']
    )
    os.makedirs(out_root, exist_ok=True)
    
    processed_chunk_path = os.path.join(out_root, processed_chunk_filename)
    sf.write(processed_chunk_path, processed_data, sample_rate, subtype = subtype) #, subtype='FLOAT') #, format='FLAC', subtype='PCM_24')
    
    # Decrement iteration count
    remaining_iterations = iteration_count - 1
    
    if remaining_iterations > 0:
        # Re-enqueue for further processing
        reenqueue_obj = {
            'chunk_index': chunk_index,
            'chunk_filename': processed_chunk_filename,
            'chunk_root': out_root,  # Now points to processed location
            'iteration_count': remaining_iterations,
            'is_first_processing': False
        }
        return reenqueue_obj
    else:
        # Processing complete
        return None

def apply_degradation_to_chunk_single(chunk_data: np.ndarray, sample_rate: int, ctx: dict) -> np.ndarray:
    """
    Apply degradation processing to a single chunk (single iteration).
    Orchestrates enabled subprocessors.
    
    Args:
        chunk_data: Stereo audio chunk [samples, 2]
        sample_rate: Audio sample rate
        ctx: Context dictionary with all processing parameters
        
    Returns:
        Processed stereo audio chunk
    """
    
    if len(chunk_data) == 0:
        return chunk_data
    
    # Start with zero output (additive processing)
    output_data = np.zeros_like(chunk_data)
    
    # Apply reverb subprocessor if enabled
    if ctx.get('reverb_enabled', True):
        reverb_processor = ReverbSubprocessor(ctx)
        reverb_output = reverb_processor.process(chunk_data, sample_rate)
        output_data += reverb_output
    else:
        # If reverb disabled, start with original signal
        output_data += chunk_data
    
    # Apply signal noise subprocessor if enabled
    if ctx.get('signal_noise_enabled', False):
        signal_noise_processor = SignalNoiseSubprocessor(ctx)
        noise_output = signal_noise_processor.process(chunk_data, sample_rate)  # Always use original signal
        output_data += noise_output
    
    return output_data