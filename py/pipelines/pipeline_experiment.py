import os
import shutil

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile
from zulu.Sda import Sda
from zulu.Sda import Channel_Mix, Channel_Left, Channel_Right, Channel_Mid, Channel_Side, Channel_Side2
from zulu.Sda import FreqOp_FullSpectrum, FreqOp_Bandpass, FreqOp_STFT

import processors_metrics
import processors_transform
import processors_visualization

PARTITION_OPTIONS = {
        "channels": [Channel_Mix],
        "time_split": True,
        "freq_ops": [FreqOp_FullSpectrum],
}

def run(profiles_root: str, profile_names: str, paths: dict):
    
    assert paths['src'] is not None, "paths['src'] is required"
    assert paths['out'] is not None, "paths['out'] is required"
    assert paths['cache'] is not None, "paths['cache'] is required"
    
    profile = ConfigCompositeProfile(profiles_root, profile_names)
    sda = Sda(profile, cache_storage = InternalStorage(paths['cache']))

    # tmp and output cleanup
    out_dir = f"{paths['out']}/exp-reverb/"
    if os.path.exists(out_dir): shutil.rmtree(out_dir)

    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)

        # fingerprint session
        out_dir = f"{paths['out']}/exp-reverb/fingerprints/"

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

        session.proc(processors_visualization.image_fingerprint)

        session.export_json_begin(f"{out_dir}/{track}.json")

        session.export_json(processors_transform.partition)
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

        session.export_files_begin(f"{out_dir}/")
        session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
        session.export_files_end()

        # transform processing - add reverb
        out_dir = f"{paths['out']}/exp-reverb/"

        session = sda.session(src_track_path)

        configJSCSS = profile.load_config()
        transform_add_reverb_config = configJSCSS.query(path_filter = processors_transform.transform_degrade.PROCESSOR_NAME, selector = None).to_graph()
        chunk_duration_sec = transform_add_reverb_config.get("chunk_duration_sec", 10)
        
        session.proc(processors_transform.partition, options=
        {
            "chunk_duration_sec": chunk_duration_sec
        })
        session.proc(processors_transform.transform_degrade)
        session.proc(processors_transform.recombine_time_chunks, options=
        {
            "chunks_source_processor_name": processors_transform.transform_degrade.PROCESSOR_NAME
        })
        
        # Gather only the final recombined file
        session.export_files_begin(out_dir)
        session.export_files(processors_transform.recombine_time_chunks, select=lambda data: (data["result"]["dir_name"], [data["result"]["file_name"]]))
        session.export_files_end()
        
    for src_track_path in sda.list_dir(source_dir = f"{paths['out']}/exp-reverb/", globs = ("*.wav", "*.mp3", "*.flac")):

        track = os.path.basename(src_track_path)
        out_dir = f"{paths['out']}/exp-reverb/fingerprints/"

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

        session.proc(processors_visualization.image_fingerprint)

        session.export_json_begin(f"{out_dir}/{track}.json")

        session.export_json(processors_transform.partition)
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

        session.export_files_begin(f"{out_dir}/")
        session.export_files(processors_visualization.image_fingerprint, select=lambda data: (data["result"]["dir_name"], data["result"]["file_names"]))
        session.export_files_end()

    # copy originals to output
    for src_track_path in sda.list_dir(source_dir = paths['src'], globs = ("*.wav", "*.mp3", "*.flac")):

        # fingerprint session
        out_dir = f"{paths['out']}/exp-reverb/"
        shutil.copy2(src_track_path, out_dir)