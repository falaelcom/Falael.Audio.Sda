ALGO_VERSION = "v001"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os

import numpy as np
import soundfile as sf
import blosc

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="cupyx.jit._interface")
import cupy as cp
from cupyx.scipy.signal import stft

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()

    assert (n_fft := config["n_fft"]) is not None
    assert (hop_length := config["hop_length"]) is not None
    assert (win_length := config["win_length"]) is not None

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),
        "_c_n_fft": n_fft,
        "_c_hop_length": hop_length,
        "_c_win_length": win_length,
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
    _, _ = os.path.splitext(out_filename)  # Discard original ext

    expected_filename = f"{out_filename}.spectrogram.blosc"
    expected_path = os.path.join(out_dir, expected_filename)
    if os.path.exists(expected_path):
        os.remove(expected_path)

    info = create_spectrogram(file_path, expected_path, n_fft, hop_length, win_length)

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "n_fft": n_fft,
            "hop_length": hop_length,
            "win_length": win_length,
            "sample_rate": info["sample_rate"],
            "shape": info["shape"],
            "dtype": info["dtype"],
            "dir_name": out_dir,
            "file_name": expected_filename,
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)
    return {"from_cache": False, "data": data}

def create_spectrogram(input_path, output_path, n_fft, hop_length, win_length):
    data, sample_rate = sf.read(input_path)
    if data.ndim > 1:
        data = np.mean(data, axis=1)  # To mono
    data = data.astype(np.float32)

    cp_data = cp.array(data)
    noverlap = win_length - hop_length
    _, _, Zxx = stft(cp_data, fs=sample_rate, nperseg=win_length, noverlap=noverlap, nfft=n_fft, window='hann', detrend=False, return_onesided=True, boundary='zeros', padded=True)

    Zxx_np = cp.asnumpy(Zxx)  # Convert to numpy for blosc
    compressed = blosc.pack_array(Zxx_np)

    with open(output_path, 'wb') as f:
        f.write(compressed)

    return {
        "shape": list(Zxx_np.shape),
        "dtype": str(Zxx_np.dtype),
        "sample_rate": sample_rate
    }