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
        "chunk_overlap_margin_ratio": 0,
        "channels": [Channel_Mix],
        "time_split": True,
        "freq_ops": [FreqOp_FullSpectrum],
}

def run(profiles_root: str, profile_names: str, paths: dict):
    
    assert paths['src'] is not None, "paths['src'] is required"
    assert paths['tmp'] is not None, "paths['tmp'] is required"
    assert paths['out'] is not None, "paths['out'] is required"
    assert paths['cache'] is not None, "paths['cache'] is required"

    profile = ConfigCompositeProfile(profiles_root, profile_names)
    configJSCSS = profile.load_config()
    configJSCSS_metric_keys_render = configJSCSS.query(path_filter = f"{processors_visualization.image_fingerprint.PROCESSOR_NAME}.METRIC_KEYS_RENDER", selector = None)
    metrics_keys_render = configJSCSS_metric_keys_render.to_graph()
    enabled_metrics = {key.split('::')[0] for key, value in metrics_keys_render.items() if value}

    sda = Sda(profile, cache_storage = InternalStorage(paths['cache']))

    # tmp and output cleanup
    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"
        if os.path.exists(out_dir): shutil.rmtree(out_dir)
        tmp_dir = f"{paths['tmp']}/1/{track}/"
        if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
        tmp_dir_width_only = f"{paths['tmp']}/2/{track}/"
        if os.path.exists(tmp_dir_width_only): shutil.rmtree(tmp_dir_width_only)

    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/{track}/"

        # fingerprint session
        session = sda.session(src_track_path)

        session.proc(processors_transform.partition, options = PARTITION_OPTIONS)

        if "base_stereo_width" in enabled_metrics:              session.proc(processors_metrics.base_stereo_width)
        if "base_stereo_phase" in enabled_metrics:              session.proc(processors_metrics.base_stereo_phase)
        if "base_stereo_correlation" in enabled_metrics:        session.proc(processors_metrics.base_stereo_correlation)
        if "base_sparkle" in enabled_metrics:                   session.proc(processors_metrics.base_sparkle)
        if "base_freq_response" in enabled_metrics:             session.proc(processors_metrics.base_freq_response)
        if "base_dynamics" in enabled_metrics:                  session.proc(processors_metrics.base_dynamics)
        if "base_dynamics_fullspectrum" in enabled_metrics:     session.proc(processors_metrics.base_dynamics_fullspectrum)
        if "base_harmonics" in enabled_metrics:                 session.proc(processors_metrics.base_harmonics)
        if "base_harmonics_fullspectrum" in enabled_metrics:    session.proc(processors_metrics.base_harmonics_fullspectrum)
        if "base_quantization" in enabled_metrics:              session.proc(processors_metrics.base_quantization)
        if "base_quantization_fullspectrum" in enabled_metrics: session.proc(processors_metrics.base_quantization_fullspectrum)
        if "calc_dynamic_range" in enabled_metrics:             session.proc(processors_metrics.calc_dynamic_range)
        if "calc_audio_quality" in enabled_metrics:             session.proc(processors_metrics.calc_audio_quality)

        session.proc(processors_visualization.image_fingerprint, options=FINGERPRINT_OPTIONS)

        session.export_json_begin(f"{out_dir}/metrics-original.json")

        if "base_stereo_width" in enabled_metrics:              session.export_json(processors_metrics.base_stereo_width)
        if "base_stereo_phase" in enabled_metrics:              session.export_json(processors_metrics.base_stereo_phase)
        if "base_stereo_correlation" in enabled_metrics:        session.export_json(processors_metrics.base_stereo_correlation)
        if "base_sparkle" in enabled_metrics:                   session.export_json(processors_metrics.base_sparkle)
        if "base_freq_response" in enabled_metrics:             session.export_json(processors_metrics.base_freq_response)
        if "base_dynamics" in enabled_metrics:                  session.export_json(processors_metrics.base_dynamics)
        if "base_dynamics_fullspectrum" in enabled_metrics:     session.export_json(processors_metrics.base_dynamics_fullspectrum)
        if "base_harmonics" in enabled_metrics:                 session.export_json(processors_metrics.base_harmonics)
        if "base_harmonics_fullspectrum" in enabled_metrics:    session.export_json(processors_metrics.base_harmonics_fullspectrum)
        if "base_quantization" in enabled_metrics:              session.export_json(processors_metrics.base_quantization)
        if "base_quantization_fullspectrum" in enabled_metrics: session.export_json(processors_metrics.base_quantization_fullspectrum)
        if "calc_dynamic_range" in enabled_metrics:             session.export_json(processors_metrics.calc_dynamic_range)
        if "calc_audio_quality" in enabled_metrics:             session.export_json(processors_metrics.calc_audio_quality)

        session.export_json_end()

        session.export_files_begin(f"{out_dir}/images-fingerprint/")
        session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
        session.export_files_end()

        # transform processing - step 2 - stereo width only (on original)
        tmp_dir_width_only = f"{paths['tmp']}/2/{track}/"

        session = sda.session(src_track_path)

        session.proc(processors_transform.transform_stereo_width_fullspectrum_fulltrack)
                    
        session.export_files_begin(tmp_dir_width_only)
        session.export_files(processors_transform.transform_stereo_width_fullspectrum_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))
        session.export_files_end()

        session.export_files_begin(f"{out_dir}/processed/")
        session.export_files(processors_transform.transform_stereo_width_fullspectrum_fulltrack, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))
        session.export_files_end()  # Note: Assumes processor renames output to avoid filename conflicts, e.g., 'transform_stereo_width_only_fulltrack.{track}'; adjust if needed.

        # width-only track fingerprint session
        width_data = session.data[processors_transform.transform_stereo_width_fullspectrum_fulltrack.PROCESSOR_NAME]
        width_corrected_file_path = os.path.join(width_data["result"]["dir_name"], width_data["result"]["file_name"])

        session = sda.session(width_corrected_file_path)

        session.proc(processors_transform.partition, options = PARTITION_OPTIONS)

        if "base_stereo_width" in enabled_metrics:              session.proc(processors_metrics.base_stereo_width)
        if "base_stereo_phase" in enabled_metrics:              session.proc(processors_metrics.base_stereo_phase)
        if "base_stereo_correlation" in enabled_metrics:        session.proc(processors_metrics.base_stereo_correlation)
        if "base_sparkle" in enabled_metrics:                   session.proc(processors_metrics.base_sparkle)
        if "base_freq_response" in enabled_metrics:             session.proc(processors_metrics.base_freq_response)
        if "base_dynamics" in enabled_metrics:                  session.proc(processors_metrics.base_dynamics)
        if "base_dynamics_fullspectrum" in enabled_metrics:     session.proc(processors_metrics.base_dynamics_fullspectrum)
        if "base_harmonics" in enabled_metrics:                 session.proc(processors_metrics.base_harmonics)
        if "base_harmonics_fullspectrum" in enabled_metrics:    session.proc(processors_metrics.base_harmonics_fullspectrum)
        if "base_quantization" in enabled_metrics:              session.proc(processors_metrics.base_quantization)
        if "base_quantization_fullspectrum" in enabled_metrics: session.proc(processors_metrics.base_quantization_fullspectrum)
        if "calc_dynamic_range" in enabled_metrics:             session.proc(processors_metrics.calc_dynamic_range)
        if "calc_audio_quality" in enabled_metrics:             session.proc(processors_metrics.calc_audio_quality)

        session.proc(processors_visualization.image_fingerprint, options=FINGERPRINT_OPTIONS)

        session.export_json_begin(f"{out_dir}/metrics-width-corrected.json")

        if "base_stereo_width" in enabled_metrics:              session.export_json(processors_metrics.base_stereo_width)
        if "base_stereo_phase" in enabled_metrics:              session.export_json(processors_metrics.base_stereo_phase)
        if "base_stereo_correlation" in enabled_metrics:        session.export_json(processors_metrics.base_stereo_correlation)
        if "base_sparkle" in enabled_metrics:                   session.export_json(processors_metrics.base_sparkle)
        if "base_freq_response" in enabled_metrics:             session.export_json(processors_metrics.base_freq_response)
        if "base_dynamics" in enabled_metrics:                  session.export_json(processors_metrics.base_dynamics)
        if "base_dynamics_fullspectrum" in enabled_metrics:     session.export_json(processors_metrics.base_dynamics_fullspectrum)
        if "base_harmonics" in enabled_metrics:                 session.export_json(processors_metrics.base_harmonics)
        if "base_harmonics_fullspectrum" in enabled_metrics:    session.export_json(processors_metrics.base_harmonics_fullspectrum)
        if "base_quantization" in enabled_metrics:              session.export_json(processors_metrics.base_quantization)
        if "base_quantization_fullspectrum" in enabled_metrics: session.export_json(processors_metrics.base_quantization_fullspectrum)
        if "calc_dynamic_range" in enabled_metrics:             session.export_json(processors_metrics.calc_dynamic_range)
        if "calc_audio_quality" in enabled_metrics:             session.export_json(processors_metrics.calc_audio_quality)

        session.export_json_end()

        session.export_files_begin(f"{out_dir}/images-fingerprint/")
        session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
        session.export_files_end()
