ALGO_VERSION = "v003" # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import subprocess

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def sub_process(parentProcessorName: str, profile: ConfigCompositeProfile, internal_storage: InternalStorage, file_path: str, pipeline_options: dict, progress_callback) -> dict:

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter=PROCESSOR_NAME, selector=None).to_graph()

    assert (sox_path := config["sox_path"]) is not None

    if not sox_path or not os.path.isfile(sox_path): raise ValueError(f"Missing or invalid '{PROCESSOR_NAME}.sox_path' value")

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),
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

    # Clean up existing channel-specific files
    expected_filename = f"{out_filename}.3_ch_mid{out_ext}"
    expected_path = os.path.join(out_dir, expected_filename)
    if os.path.exists(expected_path):
        os.remove(expected_path)

    # Create channel-specific fulltrack file
    sox_create_ch_mid(sox_path, file_path, expected_path)

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "dir_name": out_dir,
            "file_name": expected_filename
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)
    return {"from_cache": False, "data": data}

def sox_create_ch_mid(sox_path, input_path, output_path):
    cmd = [sox_path, input_path, output_path, "remix", "1v0.707,2v0.707", "channels", "1"]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"sox failed: {e.stderr.decode(errors='ignore')}")
        raise
    return cmd