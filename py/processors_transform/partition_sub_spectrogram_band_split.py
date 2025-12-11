ALGO_VERSION = "v001"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import json

import numpy as np
import blosc

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:
    """
    Performs band splitting of spectrogram files.
    """

    sub_spectrogram_extract_data_path = os.path.join(os.path.dirname(file_path), internal_storage.DATA_FILE_NAME)
    with open(sub_spectrogram_extract_data_path, 'r', encoding='utf-8') as f:
        sub_spectrogram_extract_data = json.load(f)
    sample_rate = sub_spectrogram_extract_data["result"]["sample_rate"]
    n_fft = sub_spectrogram_extract_data["result"]["n_fft"]

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config_multiband = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.multiband", selector = None).to_graph()
    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()

    assert (low_hz := int(config_multiband["cutoff_low_freqHz"])) is not None
    assert (high_hz := int(config_multiband["cutoff_high_freqHz"])) is not None
    assert (bands := int(config_multiband["bands"])) is not None

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),
        "_c_low_hz": low_hz,
        "_c_high_hz": high_hz,
        "_c_bands": bands,
        "_c_n_fft": n_fft,
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
    base_name, _ = os.path.splitext(os.path.basename(file_path))

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

    num_bins = Zxx.shape[0]
    freqs = np.fft.rfftfreq(n_fft, 1 / sample_rate)
    assert len(freqs) == num_bins

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    band_files = []
    file_masks = []

    bin_res = sample_rate / n_fft

    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]

        bin_low = int(np.ceil(f_low / bin_res))
        bin_high = int(np.floor(f_high / bin_res)) + 1

        # Low edge weight
        low_bin_center = bin_low * bin_res
        low_bin_lower = low_bin_center - bin_res / 2
        low_bin_upper = low_bin_center + bin_res / 2
        low_overlap_start = max(f_low, low_bin_lower)
        low_weight = (low_bin_upper - low_overlap_start) / bin_res if bin_low > 0 else 1.0

        # High edge weight
        high_bin_center = (bin_high - 1) * bin_res
        high_bin_lower = high_bin_center - bin_res / 2
        high_bin_upper = high_bin_center + bin_res / 2
        high_overlap_end = min(f_high, high_bin_upper)
        high_weight = (high_overlap_end - high_bin_lower) / bin_res

        # Slice, ensuring indices are valid
        bin_low = max(0, min(bin_low, num_bins))
        bin_high = max(bin_low, min(bin_high, num_bins))
        
        band_Zxx = Zxx[bin_low:bin_high, :]

        compressed_band = blosc.pack_array(band_Zxx)
        band_filename = f"{base_name}.{i:03d}.blosc"
        band_path = os.path.join(out_dir, band_filename)
        with open(band_path, 'wb') as f:
            f.write(compressed_band)

        band_files.append(band_filename)

        file_masks.append({
            "low_hz": round(f_low, 2),
            "high_hz": round(f_high, 2),
            "bin_low": bin_low,
            "bin_high": bin_high,
            "low_weight": round(low_weight, 4),
            "high_weight": round(high_weight, 4)
        })

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "low_hz": low_hz,
            "high_hz": high_hz,
            "bands": bands,
            "sample_rate": sample_rate,
            "n_fft": n_fft,
            "dir_name": out_dir,
            "file_names": band_files,
            "file_masks": file_masks
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }