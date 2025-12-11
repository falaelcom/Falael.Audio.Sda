import os
import shutil

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

from zulu.Sda import Sda
from zulu.Sda import Channel_Mix, Channel_Left, Channel_Right, Channel_Mid, Channel_Side, Channel_Side2
from zulu.Sda import FreqOp_FullSpectrum, FreqOp_Bandpass, FreqOp_STFT

import processors_transform
import processors_metrics
import processors_visualization

FINGERPRINT_OPTIONS = {
    "image_types": [["bmt", "zich"]],
    "parallel_forEach.use_processes": False,
}
MONOSTEREO_PARALLEL_OPTIONS = {
    "parallel_forEach.use_processes": False,
}
PARTITION_OPTIONS = {
        #"channels": [Channel_Mix, Channel_Left, Channel_Right, Channel_Mid, Channel_Side, Channel_Side2],
        "channels": [Channel_Mid],
        "time_split": True,
        #"freq_ops": [FreqOp_FullSpectrum, FreqOp_Bandpass],
        "freq_ops": [FreqOp_FullSpectrum, FreqOp_STFT],
}

def run(profiles_root: str, profile_names: str, paths: dict):
    
    assert paths['src'] is not None, "paths['src'] is required"
    assert paths['tmp'] is not None, "paths['tmp'] is required"
    assert paths['out'] is not None, "paths['out'] is required"
    assert paths['cache'] is not None, "paths['cache'] is required"

    sda = Sda(ConfigCompositeProfile(profiles_root, profile_names), cache_storage = InternalStorage(paths['cache']))

    # tmp and output cleanup
    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"
        if os.path.exists(out_dir): shutil.rmtree(out_dir)

    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"

        process_partition(sda, src_track_path, out_dir)

        # channels = process_mix(sda, src_track_path, out_dir)
        # process_channel(sda, channels["ch_left"], out_dir, f"1_ch_left_")
        # process_channel(sda, channels["ch_right"], out_dir, f"2_ch_right_")
        # process_channel(sda, channels["ch_mid"], out_dir, f"3_ch_mid_")
        # process_channel(sda, channels["ch_side"], out_dir, f"4_ch_side_")
        # process_channel(sda, channels["ch_side2"], out_dir, f"5_ch_side2_")

def process_partition(sda: Sda, src_track_path: str, out_dir: str):
    
    session = sda.session(src_track_path)

    session.proc(processors_transform.partition, options = PARTITION_OPTIONS)

    session.export_json_begin(f"{out_dir}/partition.json")
    session.export_json(processors_transform.partition)
    session.export_json_end()

    # session.export_files_begin(out_dir)
    # def _select_allFiles(data) -> list[str]:
    #     result = [];
    #     channels = data["result"]
    #     for channel in channels:
    #         for scope in channel:
    #             z = 1

    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Mix]["time_split"]["result"]["dir_name"], data["result"][Channel_Mix]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Mix]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Mix]["fulltrack"]["result"]["file_name"]]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Left]["time_split"]["result"]["dir_name"], data["result"][Channel_Left]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Left]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Left]["fulltrack"]["result"]["file_name"]]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Right]["time_split"]["result"]["dir_name"], data["result"][Channel_Right]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Right]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Right]["fulltrack"]["result"]["file_name"]]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Mid]["time_split"]["result"]["dir_name"], data["result"][Channel_Mid]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Mid]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Mid]["fulltrack"]["result"]["file_name"]]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Side]["time_split"]["result"]["dir_name"], data["result"][Channel_Side]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Side]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Side]["fulltrack"]["result"]["file_name"]]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Side2]["time_split"]["result"]["dir_name"], data["result"][Channel_Side2]["time_split"]["result"]["file_names"]))
    # session.export_files(processors_transform.partition, select=lambda data: (data["result"][Channel_Side2]["fulltrack"]["result"]["dir_name"], [data["result"][Channel_Side2]["fulltrack"]["result"]["file_name"]]))
    # session.export_files_end()


def process_mix(sda: Sda, src_track_path: str, out_dir: str):

    session = sda.session(src_track_path)

    session.proc(processors_transform.partition, options = PARTITION_OPTIONS)

    session.proc(processors_metrics.base_stereo_width)
    session.proc(processors_metrics.base_stereo_phase)
    session.proc(processors_metrics.base_stereo_correlation)
    session.proc(processors_metrics.base_sparkle)
    session.proc(processors_metrics.base_freq_response)
    session.proc(processors_metrics.base_dynamics)
    session.proc(processors_metrics.base_dynamics_fullspectrum)
    session.proc(processors_metrics.base_harmonics)
    session.proc(processors_metrics.base_harmonics_fullspectrum)
    session.proc(processors_metrics.base_quantization)
    session.proc(processors_metrics.base_quantization_fullspectrum)
    session.proc(processors_metrics.calc_dynamic_range)
    session.proc(processors_metrics.calc_audio_quality)

    session.proc(processors_visualization.image_fingerprint, options=FINGERPRINT_OPTIONS)

    session.export_json_begin(f"{out_dir}/metrics.json")

    session.export_json(processors_metrics.base_stereo_width)
    session.export_json(processors_metrics.base_stereo_phase)
    session.export_json(processors_metrics.base_stereo_correlation)
    session.export_json(processors_metrics.base_sparkle)
    session.export_json(processors_metrics.base_freq_response)
    session.export_json(processors_metrics.base_dynamics)
    session.export_json(processors_metrics.base_dynamics_fullspectrum)
    session.export_json(processors_metrics.base_harmonics)
    session.export_json(processors_metrics.base_harmonics_fullspectrum)
    session.export_json(processors_metrics.base_quantization)
    session.export_json(processors_metrics.base_quantization_fullspectrum)
    session.export_json(processors_metrics.calc_dynamic_range)
    session.export_json(processors_metrics.calc_audio_quality)

    session.export_json_end()

    session.export_files_begin(f"{out_dir}/images-fingerprint/")
    session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
    session.export_files_end()

    session = sda.session(src_track_path)

    session.proc(processors_transform.ch_left_extract_fulltrack)
    session.proc(processors_transform.ch_right_extract_fulltrack)
    session.proc(processors_transform.ch_mid_extract_fulltrack)
    session.proc(processors_transform.ch_side_extract_fulltrack)
    session.proc(processors_transform.ch_side2_extract_fulltrack)

    session.export_json_begin(f"{out_dir}/data.json")
    session.export_json(processors_transform.ch_left_extract_fulltrack)
    session.export_json(processors_transform.ch_right_extract_fulltrack)
    session.export_json(processors_transform.ch_mid_extract_fulltrack)
    session.export_json(processors_transform.ch_side_extract_fulltrack)
    session.export_json(processors_transform.ch_side2_extract_fulltrack)
    session.export_json_end()

    session.export_files_begin(out_dir)
    result = {}
    result["ch_left"] = session.export_files(processors_transform.ch_left_extract_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))[0]
    result["ch_right"] = session.export_files(processors_transform.ch_right_extract_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))[0]
    result["ch_mid"] = session.export_files(processors_transform.ch_mid_extract_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))[0]
    result["ch_side"] = session.export_files(processors_transform.ch_side_extract_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))[0]
    result["ch_side2"] =session.export_files(processors_transform.ch_side2_extract_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))[0]
    session.export_files_end()

    return result

def process_channel(sda: Sda, src_track_path: str, out_dir: str, prefix: str):
        
    session = sda.session(src_track_path)

    session.proc(processors_transform.partition, options = PARTITION_OPTIONS)

    session.proc(processors_metrics.base_stereo_width, options=MONOSTEREO_PARALLEL_OPTIONS)
    session.proc(processors_metrics.base_stereo_phase, options=MONOSTEREO_PARALLEL_OPTIONS)
    session.proc(processors_metrics.base_stereo_correlation, options=MONOSTEREO_PARALLEL_OPTIONS)
    session.proc(processors_metrics.base_sparkle)
    session.proc(processors_metrics.base_freq_response)
    session.proc(processors_metrics.base_dynamics)
    session.proc(processors_metrics.base_dynamics_fullspectrum)
    session.proc(processors_metrics.base_harmonics)
    session.proc(processors_metrics.base_harmonics_fullspectrum)
    session.proc(processors_metrics.base_quantization)
    session.proc(processors_metrics.base_quantization_fullspectrum)
    session.proc(processors_metrics.calc_dynamic_range)
    session.proc(processors_metrics.calc_audio_quality)

    session.proc(processors_visualization.image_fingerprint, options=FINGERPRINT_OPTIONS)

    session.export_json_begin(f"{out_dir}/{prefix}metrics.json")

    session.export_json(processors_metrics.base_stereo_width)
    session.export_json(processors_metrics.base_stereo_phase)
    session.export_json(processors_metrics.base_stereo_correlation)
    session.export_json(processors_metrics.base_sparkle)
    session.export_json(processors_metrics.base_freq_response)
    session.export_json(processors_metrics.base_dynamics)
    session.export_json(processors_metrics.base_dynamics_fullspectrum)
    session.export_json(processors_metrics.base_harmonics)
    session.export_json(processors_metrics.base_harmonics_fullspectrum)
    session.export_json(processors_metrics.base_quantization)
    session.export_json(processors_metrics.base_quantization_fullspectrum)
    session.export_json(processors_metrics.calc_dynamic_range)
    session.export_json(processors_metrics.calc_audio_quality)

    session.export_json_end()

    session.export_files_begin(f"{out_dir}/images-fingerprint/")
    session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
    session.export_files_end()
