ALGO_VERSION = "v003"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import numpy as np
import soundfile as sf

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="cupyx.jit._interface")
import cupy as cp

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

from zulu.parallel_forEach_collection import parallel_forEach_collection

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:
    """
    Splits audio into frequency bands using FFT bandpass filtering.
    Creates separate audio files for each frequency band.
    """
    
    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()
    config_multiband = configJSCSS.query(path_filter=f"{PROCESSOR_NAME}.multiband", selector=None).to_graph()
    
    assert (low_hz := int(config_multiband["cutoff_low_freqHz"])) is not None
    assert (high_hz := int(config_multiband["cutoff_high_freqHz"])) is not None
    assert (bands := int(config_multiband["bands"])) is not None

    config_accel = configJSCSS.query(path_filter=f"{PROCESSOR_NAME}.accel", selector=None).to_graph()
    config_parallel_forEach = configJSCSS.query(path_filter=f"{PROCESSOR_NAME}.parallel_forEach", selector=None).to_graph()

    assert (accel_use_cuda := config_accel["use_cuda"]) is not None
    assert (max_workers := config_parallel_forEach["max_workers"]) is not None
    assert (use_processes := config_parallel_forEach["use_processes"]) is not None
    assert (enable_parallel := config_parallel_forEach["enable"]) is not None

    #if progress_callback: progress_callback(f"partition_sub_band_split::accel_use_cuda={accel_use_cuda}")
    #if progress_callback: progress_callback(f"partition_sub_band_split::enable_parallel={enable_parallel}")
    #if progress_callback: progress_callback(f"partition_sub_band_split::max_workers={max_workers}")
    #if progress_callback: progress_callback(f"partition_sub_band_split::use_processes={use_processes}")

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),
        "_c_low_hz": low_hz,
        "_c_high_hz": high_hz,
        "_c_bands": bands,
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

    # Read audio file once
    subtype = sf.info(file_path).subtype
    data, rate = sf.read(file_path)
    if data.ndim > 1: 
        data = np.mean(data, axis=1)  # Convert to mono
    
    if accel_use_cuda:
        data = cp.array(data)
        fft = cp.fft
        freqs = cp.fft.rfftfreq(len(data), 1/rate)
    else:
        fft = np.fft
        freqs = np.fft.rfftfreq(len(data), 1/rate)
    
    # Perform FFT once for all bands
    fft_data = fft.rfft(data)
    
    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)
    
    # Prepare bands for parallel processing
    bands_to_process = []
    for i in range(bands):
        f_low = int(log_edges[i])
        f_high = int(log_edges[i + 1])
        bands_to_process.append((f_low, f_high))
    
    context = {
        'accel_use_cuda': accel_use_cuda,
        'fft_data': fft_data,
        'freqs': freqs,
        'data_len': len(data),
        'rate': rate,
        'subtype': subtype,
        'out_dir': out_dir,
        'out_filename': out_filename,
        'out_ext': out_ext,
    }
    
    # Process bands in parallel
    band_results = parallel_forEach_collection(
        bands_to_process,
        process_single_band,
        context,
        max_workers,
        use_processes=use_processes,
        enable_parallel=enable_parallel
    )
    
    # Collect and sort band files
    band_files = [result for result in band_results]
    band_files.sort(key=lambda x: int(x.split('.')[-2].split('-')[0]))
    
    bands_root = os.path.abspath(out_dir)
    
    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "low_hz": low_hz,
            "high_hz": high_hz,
            "bands": bands,
            "dir_name": bands_root,
            "file_names": band_files
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }

def process_single_band(band_index, band_info, context):
    f_low, f_high = band_info
    
    accel_use_cuda = context['accel_use_cuda']
    fft_data = context['fft_data']
    freqs = context['freqs']
    data_len = context['data_len']
    rate = context['rate']
    subtype = context['subtype']
    out_dir = context['out_dir']
    out_filename = context['out_filename']
    out_ext = context['out_ext']
    
    if accel_use_cuda: fft = cp.fft
    else: fft = np.fft

    # Create filename with frequency range
    band_filename = f"{out_filename}.{f_low:05d}-{f_high:05d}{out_ext}"
    band_path = os.path.join(out_dir, band_filename)
    
    # Remove if exists
    if os.path.exists(band_path): os.remove(band_path)
    
    # Create frequency mask for this band
    mask = (freqs >= f_low) & (freqs < f_high)
    
    # Apply mask and inverse FFT
    fft_filtered = fft_data * mask
    band_data = fft.irfft(fft_filtered, n=data_len)
    if accel_use_cuda: band_data = band_data.get()
    
    # Save bandpassed audio
    sf.write(band_path, band_data, rate, subtype = subtype) #, subtype='FLOAT') #, format='FLAC', subtype='PCM_24')
    
    return band_filename