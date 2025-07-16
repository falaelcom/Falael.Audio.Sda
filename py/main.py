import os
import sys
import time
import datetime
import glob
import json
import shutil

# modules
from x1 import split
from x2 import stereo_correlation, stereo_width, stereo_phase, sparkle, harmonics, harmonics_full_spectrum, freq_response, dynamics, dynamics_full_spectrum, quantization, quantization_full_spectrum
from x3 import dynamic_range, audio_quality
from x4 import image_fingerprint
#ALWAYS_RUN = ['audio_quality', 'harmonics', 'image_fingerprint']
#ALWAYS_RUN = ['stereo_phase']
#ALWAYS_RUN = ['image_fingerprint']
#ALWAYS_RUN = ['audio_quality', 'image_fingerprint']
ALWAYS_RUN = []
MODULES = {
    # x1
    "split": split,

    # x2
    "stereo_correlation": stereo_correlation,
    "stereo_width": stereo_width,
    "stereo_phase": stereo_phase,
    "sparkle": sparkle,
    "harmonics": harmonics,
    "harmonics_full_spectrum": harmonics_full_spectrum,
    "freq_response": freq_response,
    "dynamics": dynamics,
    "dynamics_full_spectrum": dynamics_full_spectrum,
    "quantization": quantization,
    "quantization_full_spectrum": quantization_full_spectrum,

    # x3
    "dynamic_range": dynamic_range,
    "audio_quality": audio_quality,

    # x4
    "image_fingerprint": image_fingerprint,
}

# config
OUT_DIR = "out"
SRC_DIR = "src"
CONFIG = {
    "split::duration": "0:30",
    "split::sox_path": r"..\win32\sox-14.4.2-20250323-x64\sox.exe",
    "sparkle::frame_ms": 20,
    "sparkle::min_frequency_hz": 1300,
    "stereo_phase::fft_size": 128,
    "stereo_phase::overlap": 0.5,
    "harmonics::fft_size": 4096,
    "harmonics::hop_size": 2048, 
    "harmonics_full_spectrum::fft_size": 4096,
    "harmonics_full_spectrum::hop_size": 2048, 
    "harmonics_full_spectrum::band_limit_hz": 16000,
    "freq_response::fft_size": 4096,
    "freq_response::overlap": 0.5,
    "dynamics::frame_ms": 100,
    "dynamics_full_spectrum::frame_ms": 100,
    "sinad::fft_size": 4096,
    "sinad::overlap": 0.5,
    "sinad::noise_percentile": 10,
    "multiband::cutoff_low_freqHz": 20,
    "multiband::cutoff_high_freqHz": 21000,
    "multiband::bands": 10,
    "quantization::frame_size": 1024,
    "quantization::bit_depth_tolerance": 1e-6,
    "quantization::noise_percentile": 10,
    "quantization_full_spectrum::frame_size": 1024,
    "quantization_full_spectrum::bit_depth_tolerance": 1e-6,
    "quantization_full_spectrum::noise_percentile": 10,
    "dynamic_range::noise_floor_fallback_db": -96.0,
    "audio_quality::flatness_db_floor": 0.0,
}

# app
def ensure_out_dir():
    if not os.path.exists(OUT_DIR):
        os.mkdir(OUT_DIR)
    return OUT_DIR

def get_input_files():
    if not os.path.exists(SRC_DIR):
        raise RuntimeError("Missing ./src directory")

    exts = ("*.wav", "*.mp3", "*.flac")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(SRC_DIR, ext)))
    return sorted(files)

def load_existing_results(json_path):
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load existing results from {json_path}: {e}")
    return {}

def process_file(file_path, out_path):
    filename = os.path.basename(file_path)
    
    # Create track-specific output directory: "./out/track-file-name-including-extension"
    track_output_root = os.path.join(out_path, filename)
    os.makedirs(track_output_root, exist_ok=True)
    
    # Create media subdirectory and copy source file
    media_dir = os.path.join(track_output_root, "media")
    os.makedirs(media_dir, exist_ok=True)
    copied_file_path = os.path.join(media_dir, filename)
    
    # Copy source file if not already present
    if not os.path.exists(copied_file_path):
        shutil.copy2(file_path, copied_file_path)

    # Load existing results from JSON file in track output root
    json_filename = filename + ".json"
    json_path = os.path.join(track_output_root, json_filename)
    result = load_existing_results(json_path)
    
    # If JSON loading failed, don't proceed to avoid overwriting corrupted file
    if not result and os.path.exists(json_path):
        print(f"Skipping {filename} due to corrupted JSON file. Please fix or delete {json_path}")
        return

    modules_to_run = []
    for name in MODULES.keys():
        if name not in result or name in ALWAYS_RUN:
            modules_to_run.append(name)

    # Process only missing modules
    # Pass track_output_root and copied_file_path to each module
    error_occurred = False
    for name in modules_to_run:
       module = MODULES[name]
       print(f"--- {name}")
       result[name] = module.process(copied_file_path, track_output_root, CONFIG, result)

       # Check for error
       error = result[name].get("error")
       if error:
           print(f"ERROR: {error}")
           error_occurred = True
           break

    # Save updated results only if we have valid data and no errors
    if modules_to_run and not error_occurred:
       with open(json_path, "w", encoding="utf-8") as f:
           json.dump(result, f, indent=2)

def main():
    input_files = get_input_files()

    if not input_files:
        print("No input files found.")
        return

    out_path = ensure_out_dir()

    for file_path in input_files:
        print(f"- {file_path}")
        process_file(file_path, out_path)

if __name__ == "__main__":
    main()