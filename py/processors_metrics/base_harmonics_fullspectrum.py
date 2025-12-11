ALGO_VERSION = "v001" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import processors_transform.partition as partition

import numpy as np
import soundfile as sf

from zulu.fs_cache_utils import get_file_timestamps, get_keys
from zulu.parallel_forEach_chunkCollection import parallel_forEach_chunkCollection

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:

    chunks_source_processor_name = (pipeline_options or {}).get("chunks_source_processor_name", partition.PROCESSOR_NAME)
    assert (chunks_root := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["dir_name"])
    assert (chunk_list := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["file_names"])
    assert (chunk_duration_sec := session_data[chunks_source_processor_name]["result"]["Channel_Mix"]["time_split"]["chunk_duration_sec"])

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config_parallel_forEach = configJSCSS.query(path_filter = f"{PROCESSOR_NAME}.parallel_forEach", selector = None).to_graph()
    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()

    fft_size = int(config.get("fft_size", 2048))
    step_size = int(config.get("hop_size", 1024))
    band_limit_hz = int(config.get("band_limit_hz", 16200))

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_chunk_duration_sec": chunk_duration_sec,
        "_c_chunks": get_file_timestamps(chunks_root, chunk_list),
        "_c_fft_size": fft_size,
        "_c_step_size": step_size,
        "_c_band_limit_hz": band_limit_hz,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    use_processes = config_parallel_forEach.get("use_processes", False)

    # Create context object for callback
    context = {
        'fft_size': fft_size,
        'step_size': step_size,
        'band_limit_hz': band_limit_hz
    }

    
    output = parallel_forEach_chunkCollection(_chunk_callback, chunk_list, chunks_root, context, max_workers, use_processes=use_processes)

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

def spectral_flatness(mag_spectrum):
    mag_spectrum = np.where(mag_spectrum == 0, 1e-12, mag_spectrum)
    geo_mean = np.exp(np.mean(np.log(mag_spectrum)))
    arith_mean = np.mean(mag_spectrum)
    return geo_mean / arith_mean if arith_mean != 0 else 0

def process_single_chunk(chunk_path, chunk, fft_size, step_size, band_limit_hz):
    data, rate = sf.read(chunk_path)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    spectrum_bins = int((fft_size // 2) * band_limit_hz / (rate / 2))

    flatness_values = []
    for i in range(0, len(data) - fft_size, step_size):
        frame = data[i:i+fft_size]
        windowed = frame * np.hanning(fft_size)
        mag = np.abs(np.fft.rfft(windowed))[:spectrum_bins]
        flatness_values.append(spectral_flatness(mag))

    avg_flatness = float(np.mean(flatness_values)) if flatness_values else None
    std_flatness = float(np.std(flatness_values)) if flatness_values else None
        
    return {
        "chunk": chunk,
        "overall_spectral_flatness_ratio": round(avg_flatness, 6) if avg_flatness is not None else None,
        "std_overall_spectral_flatness_ratio": round(std_flatness, 6) if std_flatness is not None else None
    }

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['fft_size'], ctx['step_size'], ctx['band_limit_hz'])

