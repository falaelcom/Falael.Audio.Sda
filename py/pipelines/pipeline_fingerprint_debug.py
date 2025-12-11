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

PARTITION_OPTIONS = {
        "channels": [Channel_Mix],
        "time_split": True,
        "freq_ops": [FreqOp_FullSpectrum],
}

def run(profiles_root: str, profile_names: str, paths: dict):
    
    assert paths['src'] is not None, "paths['src'] is required"
    assert paths['tmp'] is not None, "paths['tmp'] is required"
    assert paths['out'] is not None, "paths['out'] is required"
    assert paths['cache'] is not None, "paths['cache'] is required"
    
    cmp_dir = f"{paths['out']}/cmp/"

    sda = Sda(ConfigCompositeProfile(profiles_root, profile_names), cache_storage = InternalStorage(paths['cache']))

    # tmp and output cleanup
    if os.path.exists(cmp_dir): shutil.rmtree(cmp_dir)
    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"
        if os.path.exists(out_dir): shutil.rmtree(out_dir)
        tmp_dir = f"{paths['tmp']}/1/{track}/"
        if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)

    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"

        # fingerprint session
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

        session.export_files_begin(cmp_dir)
        session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
        session.export_files_end()
