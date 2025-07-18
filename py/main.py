import os
import sys
import time
import datetime
import glob
import json
import shutil

# modules
from x1 import split, freq_response_fulltrack, stereo_width_fulltrack
from x2 import stereo_correlation, stereo_width, stereo_phase, sparkle, harmonics, harmonics_full_spectrum, freq_response, dynamics, dynamics_full_spectrum, quantization, quantization_full_spectrum
from x3 import dynamic_range, audio_quality
from x4 import image_fingerprint, image_fulltrack

#ALWAYS_RUN = ['stereo_phase']
#ALWAYS_RUN = ['dynamics', 'dynamics_full_spectrum', 'dynamic_range', 'image_fingerprint']
#ALWAYS_RUN = ['harmonics', 'harmonics_full_spectrum', 'audio_quality', 'image_fingerprint']
#ALWAYS_RUN = ['stereo_width_fulltrack']
#ALWAYS_RUN = ['freq_response_fulltrack', 'image_fulltrack']
#ALWAYS_RUN = ['freq_response_fulltrack', 'stereo_width_fulltrack', 'image_fulltrack']
ALWAYS_RUN = []

MODULES_FINGERPRINT = {
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
    "image_fingerprint": image_fingerprint
}

MODULES_FULLTRACK = {
    # x1
    "freq_response_fulltrack": freq_response_fulltrack,
    "stereo_width_fulltrack": stereo_width_fulltrack,

    # x4
    "image_fulltrack": image_fulltrack
}

# config
OUT_DIR = "out"
SRC_DIR = "src"
CONFIG = {
    "parallel::max_workers": 16,  # or None for auto-detect

    "split::sox_path": r"..\win32\sox-14.4.2-20250323-x64\sox.exe",
    "split::duration": "0:30",

    "freq_response_fulltrack::window_samples": 4096,
    "freq_response_fulltrack::hop_samples": 2048,

    "sparkle::frame_ms": 20,
    "sparkle::min_frequency_hz": 1300,
    "stereo_phase::fft_size": 1024,
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
    "multiband::cutoff_low_freqHz": 20,
    "multiband::cutoff_high_freqHz": 21000,
    "multiband::bands": 10,
    "quantization::frame_size": 1024,
    "quantization::bit_depth_tolerance": 1e-6,
    "quantization_full_spectrum::frame_size": 1024,
    "quantization_full_spectrum::bit_depth_tolerance": 1e-6,
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

def load_all_fulltrack_results(track_output_root, filename):
    """
    Load all existing fulltrack module results and combine into unified object.
    Returns a dictionary like: {"freq_response_fulltrack": {...}, "stereo_width_fulltrack": {...}}
    """
    unified_results = {}
    
    # Load results from all known fulltrack modules
    for module_name in MODULES_FULLTRACK.keys():
        fulltrack_json_filename = f"fulltrack.{module_name}.{filename}.json"
        fulltrack_json_path = os.path.join(track_output_root, fulltrack_json_filename)
        
        if os.path.exists(fulltrack_json_path):
            module_result = load_existing_results(fulltrack_json_path)
            if module_result:
                unified_results[module_name] = module_result
    
    return unified_results

def save_fulltrack_result(track_output_root, module_name, filename, module_result):
    """
    Save a single fulltrack module's result to its individual JSON file.
    """
    fulltrack_json_filename = f"fulltrack.{module_name}.{filename}.json"
    fulltrack_json_path = os.path.join(track_output_root, fulltrack_json_filename)
    
    with open(fulltrack_json_path, "w", encoding="utf-8") as f:
        json.dump(module_result, f, indent=2)

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

    # ============================================
    # FINGERPRINT MODULES
    # ============================================
    
    # Load existing results from fingerprint JSON file
    fingerprint_json_filename = f"fingerprint.{filename}.json"
    fingerprint_json_path = os.path.join(track_output_root, fingerprint_json_filename)
    fingerprint_result = load_existing_results(fingerprint_json_path)
    
    # If JSON loading failed, don't proceed to avoid overwriting corrupted file
    if not fingerprint_result and os.path.exists(fingerprint_json_path):
        print(f"Skipping fingerprint modules for {filename} due to corrupted JSON file. Please fix or delete {fingerprint_json_path}")
        return

    fingerprint_modules_to_run = []
    for name in MODULES_FINGERPRINT.keys():
        if name not in fingerprint_result or name in ALWAYS_RUN:
            fingerprint_modules_to_run.append(name)

    # Process fingerprint modules
    for name in fingerprint_modules_to_run:
        module = MODULES_FINGERPRINT[name]
        print(f"--- {name}")
        fingerprint_result[name] = module.process(copied_file_path, track_output_root, CONFIG, fingerprint_result)

    # Save fingerprint results
    if fingerprint_modules_to_run:
        with open(fingerprint_json_path, "w", encoding="utf-8") as f:
            json.dump(fingerprint_result, f, indent=2)

    # ============================================
    # FULLTRACK MODULES
    # ============================================
    
    # Process each fulltrack module with unified previous results
    for name in MODULES_FULLTRACK.keys():
        module = MODULES_FULLTRACK[name]
        
        # Check if module should be skipped
        fulltrack_json_filename = f"fulltrack.{name}.{filename}.json"
        fulltrack_json_path = os.path.join(track_output_root, fulltrack_json_filename)
        
        if os.path.exists(fulltrack_json_path) and name not in ALWAYS_RUN:
            continue
            
        print(f"--- {name}")
        
        # Load all existing fulltrack results into unified object
        unified_fulltrack_results = load_all_fulltrack_results(track_output_root, filename)
        
        # Combine fingerprint and fulltrack results for the module
        # Module receives fingerprint results + any existing fulltrack results
        combined_previous = fingerprint_result.copy()
        combined_previous.update(unified_fulltrack_results)
        
        # Process the module with unified previous results
        module_result = module.process(copied_file_path, track_output_root, CONFIG, combined_previous)
        
        # Save only this module's result to its individual file
        save_fulltrack_result(track_output_root, name, filename, module_result)

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