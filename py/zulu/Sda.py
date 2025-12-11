import os
import time
import json
import shutil
import glob

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="cupyx.jit._interface")
import cupy
if not cupy.cuda.Device(0).use(): print(); print("No CUDA driver found"); print()

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

# from zulu.Sda import Sda, SdaSession
# from zulu.Sda import Channel_Mix, Channel_Left, Channel_Right, Channel_Mid, Channel_Side, Channel_Side2
# from zulu.Sda import FreqOp_FullSpectrum, FreqOp_Bandpass, FreqOp_STFT

Channel_Mix = "Channel_Mix"
Channel_Left = "Channel_Left"
Channel_Right = "Channel_Right"
Channel_Mid = "Channel_Mid"
Channel_Side = "Channel_Side"
Channel_Side2 = "Channel_Side2"

FreqOp_FullSpectrum = "FreqOp_FullSpectrum"                     # no frequency domain processing
FreqOp_Bandpass = "FreqOp_Bandpass"             # produce frequency spectrum array and bandpass-filtered audio tracks (FFT → mask → IFFT)
FreqOp_STFT = "FreqOp_STFT"                     # produce spectrogram 2D array of the full track spectrum

def _progress_callback(text: str = None) -> None:
    if not text:
        print()
    else:
        print(f"----- {text}")

class SdaSession:
    def __init__(self, sda, file_path: str):
        self.sda = sda
        self.file_path = file_path
        
        self.data = {}
        self.aggregate_data = {}
        self.out_current_json_file_path = None
        self.out_current_json_data = None
        self.out_current_file_dest_dir = None

    def proc(self, processor, options: dict = None) -> None:
        
        processor_name = processor.PROCESSOR_NAME
        
        configJSCSS = self.sda.profile.load_config()
        if options: configJSCSS.cascade_graph({processor_name: options})

        config_parallel_forEach = configJSCSS.query(path_filter = processor_name + ".parallel_forEach", selector = None).to_graph()
        assert (enable_parallel := config_parallel_forEach["enable"]) is not None
        if enable_parallel == False:
            max_workers_text = ""
            use_processes_text = "SYNC"
        else:
            assert (max_workers := config_parallel_forEach["max_workers"]) is not None
            max_workers_text = str(max_workers) + " wks"
            assert (use_processes := config_parallel_forEach["use_processes"]) is not None
            use_processes = config_parallel_forEach.get("use_processes", None)
            if use_processes: 
                use_processes_text = "PROC"
            else: 
                use_processes_text = "THRD"
            
        print(f"--- {processor_name:<40} | {use_processes_text:<6} | {max_workers_text:<6} | ", end="", flush=True)
   
        start_time = time.time()
        outcome = processor.process(self.sda.profile, self.sda.cache_storage, self.data, self.file_path, options, _progress_callback)
        end_time = time.time()
        self.data[processor_name] = outcome["data"]
   
        execution_time = end_time - start_time
        minutes = int(execution_time // 60)
        seconds = execution_time % 60
        time_str = f"{minutes:02d}:{seconds:06.3f}"
   
        if outcome["from_cache"]: 
            print("cache")
        else:
            print(time_str)

    def export_json_begin(self, out_path: str):
        self.out_current_json_file_path = out_path
        self.out_current_json_data = {}

    def export_json(self, processor):
        self.out_current_json_data[processor.PROCESSOR_NAME] = self.data[processor.PROCESSOR_NAME];

    def export_json_end(self):
        dest_file_dir = os.path.dirname(self.out_current_json_file_path)
        os.makedirs(dest_file_dir, exist_ok=True)
        with open(self.out_current_json_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.out_current_json_data, f, indent=2, ensure_ascii=False)
        self.out_current_json_file_path = None
        self.out_current_json_data = None

    def export_files_begin(self, out_path: str):
        self.out_current_file_dest_dir = out_path

    def export_files(self, processor, select):
        result = []
        processor_data = self.data[processor.PROCESSOR_NAME]
        (root_dir, file_list) = select(processor_data)
        for expfi_file_path in file_list:
            src_file_path = os.path.join(root_dir, expfi_file_path)
            dest_file_path = os.path.join(self.out_current_file_dest_dir, expfi_file_path)
            dest_file_dir = os.path.dirname(dest_file_path)
            os.makedirs(dest_file_dir, exist_ok=True)
            shutil.copy2(src_file_path, dest_file_path)
            result.append(src_file_path)
        return result

    def export_files_end(self):
        self.out_current_file_dest_dir = None

class Sda:
    def __init__(self, profile: ConfigCompositeProfile, cache_storage: InternalStorage):
        self.profile = profile
        self.cache_storage = cache_storage

    def list_dir(self, source_dir: str, globs) -> list[str]:
        result = []
        for ext in globs:
            result.extend(glob.glob(os.path.join(source_dir, ext)))
        result = sorted(result)
        return result
        
    def clear_cache(self, processor):

        self.cache_storage.remove(processor_name = processor.PROCESSOR_NAME)

    def session(self, file_path: str): 
        print()
        print(f"- {file_path}")
        print("-------------------------------------------------------------------------")
        return SdaSession(self, file_path)
