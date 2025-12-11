ALGO_VERSION = "v002"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import soundfile as sf
import glob

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:
    """
    Performs the actual time splitting of audio files manually.
    
    Args:
        internal_storage: Storage for caching files
        file_path: Path to the audio file to split
        chunk_duration_sec: Duration of each chunk in seconds
        params_version: Version string for cache management
    
    Returns:
        Dictionary with chunk files information
    """
    
    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()

    assert (chunk_duration_sec := config["chunk_duration_sec"]) is not None
    assert (chunk_overlap_margin_ratio := config["chunk_overlap_margin_ratio"]) is not None
    assert (sample_rounding_policy := config["sample_rounding_policy"]) is not None

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),
        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunk_overlap_margin_ratio": chunk_overlap_margin_ratio,
        "_c_sample_rounding_policy": sample_rounding_policy,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    out_dir = internal_storage.get_root_dir(PROCESSOR_NAME, ALGO_VERSION, new_params_version)
    os.makedirs(out_dir, exist_ok=True)
    out_filename = os.path.basename(file_path)
    _, out_ext = os.path.splitext(out_filename)

    # Delete existing output files before processing
    i = 0
    while True:
        expected_filename = f"{out_filename}.{i:03d}{out_ext}"
        expected_path = os.path.join(out_dir, expected_filename)
        if os.path.exists(expected_path):
            os.remove(expected_path)
            i += 1
        else:
            break

    # Read the audio file
    subtype = sf.info(file_path).subtype
    data, sample_rate = sf.read(file_path)
    total_samples = len(data)

    # Convert to samples early
    chunk_samples = round_to_samples(chunk_duration_sec * 1000, sample_rate, sample_rounding_policy)
    margin_samples = round_to_samples(chunk_overlap_margin_ratio * chunk_duration_sec * 1000, sample_rate, sample_rounding_policy)

    chunk_files = []
    file_masks = []

    current_start_sample = 0
    chunk_index = 0

    while current_start_sample < total_samples:
        is_first = (chunk_index == 0)
        remaining_samples = total_samples - current_start_sample

        # Determine chunk total samples
        if is_first:
            total_chunk_samples = chunk_samples + margin_samples
        else:
            total_chunk_samples = chunk_samples + 2 * margin_samples

        # For last chunk, adjust if necessary
        if current_start_sample + total_chunk_samples > total_samples:
            total_chunk_samples = remaining_samples
            # Trim margin if needed for last chunk
            if not is_first:
                effective_margin_samples = max(0, (remaining_samples - chunk_samples) // 2)
                total_chunk_samples = chunk_samples + 2 * effective_margin_samples
                if remaining_samples - total_chunk_samples > 0:
                    total_chunk_samples += 1  # Add remainder if odd

        # Ensure we don't exceed total samples
        total_chunk_samples = min(total_chunk_samples, remaining_samples)

        # Extract chunk data
        chunk_data = data[current_start_sample : current_start_sample + total_chunk_samples]

        # Write chunk file
        chunk_filename = f"{out_filename}.{chunk_index:03d}{out_ext}"
        chunk_path = os.path.join(out_dir, chunk_filename)
        sf.write(chunk_path, chunk_data, sample_rate, subtype = subtype) #, subtype='FLOAT') #, format='FLAC', subtype='PCM_24')

        chunk_files.append(chunk_filename)

        # Calculate mask (core region)
        if is_first:
            mask_start_sample = 0
        else:
            mask_start_sample = margin_samples

        # Mask length: chunk duration, but for last chunk, adjust if total < expected
        expected_mask_length_samples = chunk_samples
        actual_mask_length_samples = min(expected_mask_length_samples, total_chunk_samples - mask_start_sample)
        # For non-first, check end margin
        if not is_first:
            end_margin_samples = total_chunk_samples - (mask_start_sample + actual_mask_length_samples)
            if end_margin_samples < margin_samples:
                # Adjust if trimmed
                actual_mask_length_samples = total_chunk_samples - mask_start_sample - end_margin_samples

        # Derive ms values
        total_duration_ms = round_to_ms(total_chunk_samples, sample_rate, sample_rounding_policy)
        mask_start_ms = round_to_ms(mask_start_sample, sample_rate, sample_rounding_policy)
        mask_length_ms = round_to_ms(actual_mask_length_samples, sample_rate, sample_rounding_policy)

        file_masks.append({
            "total_duration_ms": total_duration_ms,
            "total_samples": total_chunk_samples,
            "mask_start_ms": mask_start_ms,
            "mask_start_samples": mask_start_sample,
            "mask_length_ms": mask_length_ms,
            "mask_length_samples": actual_mask_length_samples
        })

        # Advance start for next chunk
        current_start_sample += chunk_samples
        chunk_index += 1

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "chunk_duration_sec": chunk_duration_sec,
            "chunk_overlap_margin_ratio": chunk_overlap_margin_ratio,
            "sample_rounding_policy": sample_rounding_policy,
            "sample_rate": sample_rate,
            "dir_name": out_dir,
            "file_names": chunk_files,
            "file_masks": file_masks
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }

def round_to_samples(time_ms: float, sample_rate: int, policy: str) -> int:
    """
    Utility function to round time in ms to nearest sample count based on policy.
    """
    samples_float = (time_ms / 1000.0) * sample_rate
    if policy == "PythonRound3+":
        return round(samples_float)
    else:
        raise ValueError(f"Unsupported sample_rounding_policy: {policy}")

def round_to_ms(samples: int, sample_rate: int, policy: str) -> int:
    """
    Utility function to round sample count to nearest ms based on policy.
    """
    ms_float = (samples / sample_rate) * 1000.0
    if policy == "PythonRound3+":
        return round(ms_float)
    else:
        raise ValueError(f"Unsupported sample_rounding_policy: {policy}")