#ALGO_VERSION = "v001"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os

from processors_transform.partition_sub_time_split import sub_process as sub_time_split
from processors_transform.partition_sub_ch_left_extract import sub_process as sub_ch_left_extract
from processors_transform.partition_sub_ch_right_extract import sub_process as sub_ch_right_extract
from processors_transform.partition_sub_ch_mid_extract import sub_process as sub_ch_mid_extract
from processors_transform.partition_sub_ch_side_extract import sub_process as sub_ch_side_extract
from processors_transform.partition_sub_ch_side2_extract import sub_process as sub_ch_side2_extract
from processors_transform.partition_sub_band_split import sub_process as sub_band_split
from processors_transform.partition_sub_spectrogram_extract import sub_process as sub_spectrogram_extract
from processors_transform.partition_sub_spectrogram_band_split import sub_process as sub_spectrogram_band_split
from processors_transform.partition_sub_spectrogram_time_split import sub_process as sub_spectrogram_time_split

from zulu.fs_cache_utils import get_file_timestamp, get_keys
from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

from zulu.Sda import Sda, SdaSession
from zulu.Sda import Channel_Mix, Channel_Left, Channel_Right, Channel_Mid, Channel_Side, Channel_Side2
from zulu.Sda import FreqOp_FullSpectrum, FreqOp_Bandpass, FreqOp_STFT

from zulu.parallel_forEach_collection import parallel_forEach_collection

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:
    
    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()
    assert (channels := config["channels"]) is not None
    assert (time_split := config["time_split"]) is not None
    assert (freq_ops := config["freq_ops"]) is not None

    config_parallel_forEach_sub_ch = configJSCSS.query(path_filter=f"{PROCESSOR_NAME}.parallel_forEach.sub_ch", selector=None).to_graph()

    assert (max_workers_sub_ch := config_parallel_forEach_sub_ch["max_workers"]) is not None
    assert (use_processes_sub_ch := config_parallel_forEach_sub_ch["use_processes"]) is not None
    assert (enable_parallel_sub_ch := config_parallel_forEach_sub_ch["enable"]) is not None

    config_parallel_forEach_sub_time_split = configJSCSS.query(path_filter=f"{PROCESSOR_NAME}.parallel_forEach.sub_time_split", selector=None).to_graph()

    assert (max_workers_sub_time_split := config_parallel_forEach_sub_time_split["max_workers"]) is not None
    assert (use_processes_sub_time_split := config_parallel_forEach_sub_time_split["use_processes"]) is not None
    assert (enable_parallel_sub_time_split := config_parallel_forEach_sub_time_split["enable"]) is not None

    channels_to_process = channels

    context = {
        "profile": profile,
        "internal_storage": internal_storage,
        "file_path": file_path,
        "pipeline_options": pipeline_options,
        "progress_callback": progress_callback,
        "time_split": time_split,
        "freq_ops": freq_ops,
        "max_workers_sub_time_split": max_workers_sub_time_split,
        "use_processes_sub_time_split": use_processes_sub_time_split,
        "enable_parallel_sub_time_split": enable_parallel_sub_time_split,
    }

    if progress_callback: progress_callback()

    channel_outcomes = parallel_forEach_collection(
        channels_to_process,
        process_single_channel,
        context,
        max_workers_sub_ch,
        use_processes=use_processes_sub_ch,
        enable_parallel=enable_parallel_sub_ch
    )

    if progress_callback: progress_callback()

    sorted_outcomes = sorted(channel_outcomes, key=lambda x: channels.index(x["name"]))

    result = {}
    for item in sorted_outcomes:
        result[item["name"]] = item["result"]

    from_cache = all(item["from_cache"] for item in channel_outcomes)

    data = {
        "result": result
    }

    return {
        "from_cache": from_cache,
        "data": data
    }

def process_single_channel(item_index, channel_name, context):
    profile = context["profile"]
    internal_storage = context["internal_storage"]
    file_path = context["file_path"]
    pipeline_options = context["pipeline_options"]
    progress_callback = context["progress_callback"]
    time_split = context["time_split"]
    freq_ops = context["freq_ops"]
    max_workers_sub_time_split = context["max_workers_sub_time_split"]
    use_processes_sub_time_split = context["use_processes_sub_time_split"]
    enable_parallel_sub_time_split = context["enable_parallel_sub_time_split"]

    if channel_name == Channel_Mix:
        (params, new_params_version) = get_keys({
            "_c_src_file_name": os.path.basename(file_path),
            "_c_src_file_timestamp": get_file_timestamp(file_path),
        })
        outcome = {
            "from_cache": True,
            "data": {
                "params_version": new_params_version,
                "params": params,
                "result": {
                    "dir_name": os.path.dirname(file_path),
                    "file_name": os.path.basename(file_path)
                }
            }
        }
    elif channel_name == Channel_Left: 
        outcome = sub_ch_left_extract(PROCESSOR_NAME, profile, internal_storage, file_path, pipeline_options, progress_callback)
    elif channel_name == Channel_Right: 
        outcome = sub_ch_right_extract(PROCESSOR_NAME, profile, internal_storage, file_path, pipeline_options, progress_callback)
    elif channel_name == Channel_Mid: 
        outcome = sub_ch_mid_extract(PROCESSOR_NAME, profile, internal_storage, file_path, pipeline_options, progress_callback)
    elif channel_name == Channel_Side: 
        outcome = sub_ch_side_extract(PROCESSOR_NAME, profile, internal_storage, file_path, pipeline_options, progress_callback)
    elif channel_name == Channel_Side2: 
        outcome = sub_ch_side2_extract(PROCESSOR_NAME, profile, internal_storage, file_path, pipeline_options, progress_callback)
    else: raise ValueError(channel_name)

    channel_from_cache = outcome["from_cache"]
    channel_dir_name = outcome["data"]["result"]["dir_name"]
    channel_file_name = outcome["data"]["result"]["file_name"]
    channel_file_path = os.path.join(channel_dir_name, channel_file_name)
    if progress_callback: progress_callback(f"{channel_name}...")

    channel_result = {}

    if FreqOp_FullSpectrum in freq_ops:
        channel_result["fulltrack"] = outcome["data"]["result"]
        if time_split:
            # if progress_callback: progress_callback(f"{channel_name} - time split...")
            ts_outcome = sub_time_split(PROCESSOR_NAME, profile, internal_storage, channel_file_path, pipeline_options, progress_callback)
            channel_result["time_split"] = ts_outcome["data"]["result"]
            if not ts_outcome["from_cache"]: channel_from_cache = False
            # if progress_callback: progress_callback(f"{channel_name} - time split - Done.")

    if FreqOp_Bandpass in freq_ops:
        # if progress_callback: progress_callback(f"{channel_name} - band split...")
        bs_outcome = sub_band_split(PROCESSOR_NAME, profile, internal_storage, channel_file_path, pipeline_options, progress_callback)
        channel_result["band_split"] = bs_outcome["data"]["result"]
        if not bs_outcome["from_cache"]: channel_from_cache = False
        # if progress_callback: progress_callback(f"{channel_name} - band split - Done.")
        if time_split:
            band_dir = channel_result["band_split"]["dir_name"]
            band_files = channel_result["band_split"]["file_names"]
            band_files_to_process = band_files
            context_band_ts = {
                "profile": profile,
                "internal_storage": internal_storage,
                "pipeline_options": pipeline_options,
                "progress_callback": progress_callback,
                "channel_name": channel_name,
                "band_dir": band_dir
            }
            bts_results = parallel_forEach_collection(
                band_files_to_process,
                process_single_band_time_split,
                context_band_ts,
                max_workers_sub_time_split,
                use_processes=use_processes_sub_time_split,
                enable_parallel=enable_parallel_sub_time_split
            )
            sorted_bts_results = sorted(bts_results, key=lambda x: band_files.index(x["band_file"]))
            for result in sorted_bts_results:
                bts_outcome = result["outcome"]
                if not "band_time_split" in channel_result: 
                    channel_result["band_time_split"] = {
                        "band_split": [],
                    }
                    for key in bts_outcome["data"]["result"]:
                        if key in ["dir_name", "file_names"]: continue
                        channel_result["band_time_split"][key] = bts_outcome["data"]["result"][key]
                    for key in channel_result["band_split"]:
                        if key in ["dir_name", "file_names"]: continue
                        channel_result["band_time_split"][key] = channel_result["band_split"][key]
                channel_result["band_time_split"]["band_split"].append({
                    "dir_name": result["dir_name"],
                    "file_names": result["file_names"],
                })
                if not bts_outcome["from_cache"]: channel_from_cache = False

    if FreqOp_STFT in freq_ops:

        #raise RuntimeError("NEEDS MASSIVE TESTING of")
        #raise RuntimeError("- partition_sub_spectrogram_extract.py")
        #raise RuntimeError("- partition_sub_spectrogram_band_split.py")
        #raise RuntimeError("- partition_sub_spectrogram_time_split.py")
        #raise RuntimeError("Best validate with a new module image_spectrogram.py")

        if progress_callback: progress_callback(f"{channel_name} - spectrogram...")
        spectrogram_outcome = sub_spectrogram_extract(PROCESSOR_NAME, profile, internal_storage, channel_file_path, pipeline_options, progress_callback)
        if progress_callback: progress_callback(f"{channel_name} - spectrogram - Done.")
        if FreqOp_FullSpectrum in freq_ops:
            channel_result["spectrogram"] = spectrogram_outcome["data"]["result"]
            if not spectrogram_outcome["from_cache"]: channel_from_cache = False
        if time_split:
            if progress_callback: progress_callback(f"{channel_name} - spectrogram time split...")
            spectrogram_ts_outcome = sub_spectrogram_time_split(PROCESSOR_NAME, profile, internal_storage, os.path.join(spectrogram_outcome["data"]["result"]["dir_name"], spectrogram_outcome["data"]["result"]["file_name"]), pipeline_options, progress_callback)
            if progress_callback: progress_callback(f"{channel_name} - spectrogram time split - Done.")
            if FreqOp_FullSpectrum in freq_ops:
                channel_result["spectrogram_time_split"] = spectrogram_ts_outcome["data"]["result"]
                if not spectrogram_ts_outcome["from_cache"]: channel_from_cache = False
            if FreqOp_Bandpass in freq_ops:
                channel_result["spectrogram_time_band_split"] = []
                for i, file in enumerate(spectrogram_ts_outcome["data"]["result"]["file_names"]):
                    mask = spectrogram_ts_outcome["data"]["result"]["file_masks"][i]
                    if progress_callback: progress_callback(f"{channel_name} - spectrogram band time split...")
                    spectrogram_bs_outcome = sub_spectrogram_band_split(PROCESSOR_NAME, profile, internal_storage, os.path.join(spectrogram_ts_outcome["data"]["result"]["dir_name"], file), pipeline_options, progress_callback)
                    if progress_callback: progress_callback(f"{channel_name} - spectrogram band time split - Done.")
                    channel_result["spectrogram_time_band_split"].extend(spectrogram_bs_outcome["data"]["result"])
                    if not spectrogram_bs_outcome["from_cache"]: channel_from_cache = False
        elif FreqOp_Bandpass in freq_ops:
            if progress_callback: progress_callback(f"{channel_name} - spectrogram band split...")
            spectrogram_bs_outcome = sub_spectrogram_band_split(PROCESSOR_NAME, profile, internal_storage, os.path.join(spectrogram_outcome["data"]["result"]["dir_name"], spectrogram_outcome["data"]["result"]["file_name"]), pipeline_options, progress_callback)
            channel_result["spectrogram_time_split"] = spectrogram_bs_outcome["data"]["result"]
            if not spectrogram_bs_outcome["from_cache"]: channel_from_cache = False
            if progress_callback: progress_callback(f"{channel_name} - spectrogram band split - Done.")

    return {
        "name": channel_name,
        "from_cache": channel_from_cache,
        "result": channel_result
    }

def process_single_band_time_split(item_index, band_file, context):
    band_file_path = os.path.join(context["band_dir"], band_file)
    # if context["progress_callback"]: context["progress_callback"](f"{context['channel_name']} - band time split...")
    bts_outcome = sub_time_split(PROCESSOR_NAME, context["profile"], context["internal_storage"], band_file_path, context["pipeline_options"], context["progress_callback"])
    # if context["progress_callback"]: context["progress_callback"](f"{context['channel_name']} - band time split - Done.")
    return {
        "band_file": band_file,
        "outcome": bts_outcome,
        "dir_name": bts_outcome["data"]["result"]["dir_name"],
        "file_names": bts_outcome["data"]["result"]["file_names"]
    }
