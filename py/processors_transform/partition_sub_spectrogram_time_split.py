ALGO_VERSION = "v002"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import json

import numpy as np
import blosc
import soundfile as sf  # For sample_rate if not in info

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:
    """
    Performs time splitting of spectrogram files.
    """

    sub_spectrogram_extract_data_path = os.path.join(os.path.dirname(file_path), internal_storage.DATA_FILE_NAME)
    with open(sub_spectrogram_extract_data_path, 'r', encoding='utf-8') as f:
        sub_spectrogram_extract_data = json.load(f)
    sample_rate = sub_spectrogram_extract_data["result"]["sample_rate"]
    hop_length = sub_spectrogram_extract_data["result"]["hop_length"]

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
    base_name, _ = os.path.splitext(out_filename)

    # Delete existing output files
    i = 0
    while True:
        expected_filename = f"{base_name}.{i:03d}.blosc"
        expected_path = os.path.join(out_dir, expected_filename)
        if os.path.exists(expected_path):
            os.remove(expected_path)
            i += 1
        else:
            break

    # Load spectrogram
    with open(file_path, 'rb') as f:
        compressed = f.read()
    Zxx = blosc.unpack_array(compressed)

    total_frames = Zxx.shape[1]

    # Convert to frames
    chunk_frames = round_to_frames(chunk_duration_sec * 1000, sample_rate, hop_length, sample_rounding_policy)
    margin_frames = round_to_frames(chunk_overlap_margin_ratio * chunk_duration_sec * 1000, sample_rate, hop_length, sample_rounding_policy)

    chunk_files = []
    file_masks = []

    current_start_frame = 0
    chunk_index = 0

    while current_start_frame < total_frames:
        is_first = (chunk_index == 0)
        remaining_frames = total_frames - current_start_frame

        if is_first:
            total_chunk_frames = chunk_frames + margin_frames
        else:
            total_chunk_frames = chunk_frames + 2 * margin_frames

        if current_start_frame + total_chunk_frames > total_frames:
            total_chunk_frames = remaining_frames
            if not is_first:
                effective_margin_frames = max(0, (remaining_frames - chunk_frames) // 2)
                total_chunk_frames = chunk_frames + 2 * effective_margin_frames
                if remaining_frames - total_chunk_frames > 0:
                    total_chunk_frames += 1

        total_chunk_frames = min(total_chunk_frames, remaining_frames)

        # Slice spectrogram
        chunk_Zxx = Zxx[:, current_start_frame : current_start_frame + total_chunk_frames]

        # Compress and write
        compressed_chunk = blosc.pack_array(chunk_Zxx)
        chunk_filename = f"{base_name}.{chunk_index:03d}.blosc"
        chunk_path = os.path.join(out_dir, chunk_filename)
        with open(chunk_path, 'wb') as f:
            f.write(compressed_chunk)

        chunk_files.append(chunk_filename)

        # Calculate mask
        if is_first:
            mask_start_frame = 0
        else:
            mask_start_frame = margin_frames

        expected_mask_length_frames = chunk_frames
        actual_mask_length_frames = min(expected_mask_length_frames, total_chunk_frames - mask_start_frame)
        if not is_first:
            end_margin_frames = total_chunk_frames - (mask_start_frame + actual_mask_length_frames)
            if end_margin_frames < margin_frames:
                actual_mask_length_frames = total_chunk_frames - mask_start_frame - end_margin_frames

        # Derive ms values
        total_duration_ms = round_to_ms_from_frames(total_chunk_frames, sample_rate, hop_length, sample_rounding_policy)
        mask_start_ms = round_to_ms_from_frames(mask_start_frame, sample_rate, hop_length, sample_rounding_policy)
        mask_length_ms = round_to_ms_from_frames(actual_mask_length_frames, sample_rate, hop_length, sample_rounding_policy)

        file_masks.append({
            "total_duration_ms": total_duration_ms,
            "total_frames": total_chunk_frames,
            "mask_start_ms": mask_start_ms,
            "mask_start_frames": mask_start_frame,
            "mask_length_ms": mask_length_ms,
            "mask_length_frames": actual_mask_length_frames
        })

        current_start_frame += chunk_frames
        chunk_index += 1

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "chunk_duration_sec": chunk_duration_sec,
            "chunk_overlap_margin_ratio": chunk_overlap_margin_ratio,
            "sample_rounding_policy": sample_rounding_policy,
            "sample_rate": sample_rate,  # For consistency
            "hop_length": hop_length,
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

def round_to_frames(time_ms: float, sample_rate: int, hop_length: int, policy: str) -> int:
    samples_float = (time_ms / 1000.0) * sample_rate
    frames_float = samples_float / hop_length
    if policy == "PythonRound3+":
        return round(frames_float)
    else:
        raise ValueError(f"Unsupported sample_rounding_policy: {policy}")

def round_to_ms_from_frames(frames: int, sample_rate: int, hop_length: int, policy: str) -> int:
    samples = frames * hop_length
    ms_float = (samples / sample_rate) * 1000.0
    if policy == "PythonRound3+":
        return round(ms_float)
    else:
        raise ValueError(f"Unsupported sample_rounding_policy: {policy}")
