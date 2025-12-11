CONFIG = {
    "*": {
		"accel.use_cuda": True,

        "parallel_forEach.enable": True,
        "parallel_forEach.max_workers": 16,    # or None for auto-detect
        "parallel_forEach.use_processes": True,
        
        # changing this values will most likely require also to change normalization functions
        "multiband.cutoff_low_freqHz": 20,
        "multiband.cutoff_high_freqHz": 21000,
        "multiband.bands": 10,

        "sox_path": r"..\win32\sox-14.4.2-20250323-x64\sox.exe",
    },
    
    "partition": {
        "parallel_forEach.sub_ch.enable": False,
        "parallel_forEach.sub_ch.use_processes": True,
        "parallel_forEach.sub_ch.max_workers": 2,

        "parallel_forEach.sub_time_split.enable": True,
        "parallel_forEach.sub_time_split.use_processes": False,
        "parallel_forEach.sub_time_split.max_workers": 12,
    },
    "partition_sub_band_split": {
        "parallel_forEach.enable": False,
        "parallel_forEach.use_processes": True,
        "parallel_forEach.max_workers": 2,
    },
    "partition_sub_time_split": {
        "chunk_duration_sec": 30.0, # changing this value will most likely require also to change normalization functions
        "chunk_overlap_margin_ratio": 1,
        "sample_rounding_policy": "PythonRound3+",
    },
    "partition_sub_spectrogram_extract": {
        "parallel_forEach.enable": False,

        "n_fft": 2048,
        "hop_length": 512,
        "win_length": 2048,
    },
    "partition_sub_spectrogram_time_split": {
        "parallel_forEach.enable": False,

        "chunk_duration_sec": 30.0, # changing this value will most likely require also to change normalization functions
        "chunk_overlap_margin_ratio": 1,
        "sample_rounding_policy": "PythonRound3+",
    },
    "partition_sub_spectrogram_band_split": {
        "parallel_forEach.enable": False,
        
        "n_fft": 2048,
    },

    "recombine_time_chunks": {
        "parallel_forEach.enable": False,
    },
    "base_freq_response_fulltrack": {
        "parallel_forEach.enable": False,

        "window_samples": 4096,
        "hop_samples": 2048,
    },
    "base_stereo_width_fulltrack": {
        "parallel_forEach.use_processes": True,
    },
    "transform_stereo_width_fullspectrum_fulltrack":
    {
        "parallel_forEach.enable": False,

        "correction_fn": "linear",  # "linear" or "exponential"
        "vertical_translation": 0.0,
        "x_1": 0.95,      # "exponential" only
        "flatness": 1,    # "exponential" only
        "slope": 0.65,    # "linear" only
        "min_freq_hz": 200,
        "max_freq_hz": 15000,
        "bell_curve_decay_speed": 2.2,
        "window_samples": 4096,
        "hop_samples": 2048,
        "window_type": "hann",
    },
    "transform_degrade": {
        "parallel_forEach.use_processes": True,

        # Debug mode - prints detailed reverb generation info
        "debug_mode": True,
    
        # Cascade mode - each chunk gets more reverb iterations (chunk 1=1x, chunk 2=2x, etc.)
        "cascade_mode": True,

        # Frequency range for multiband processing
        "multiband.low_hz": 20,
        "multiband.high_hz": 21000,
    
        # Number of frequency bands (3 = low/mid/high split)
        "multiband.bands": 3,

        # Length of each audio chunk processed separately (shorter = more gradual cascade progression)
        "chunk_duration_sec": 2.5,
    
        # Room dimensions in meters - create specific delay times and resonant frequencies
        "room_width": 15.0,    # Side-to-side spaciousness (~44ms delay, ~23Hz resonance)
        "room_height": 8.0,    # Vertical dimension (~23ms delay, ~43Hz resonance)  
        "room_depth": 25.0,    # Front-back depth (~73ms delay, ~14Hz resonance, longest echoes)
    
        # Number of comb filters - more = smoother, less metallic reverb character (6 is good balance)
        "num_comb_filters": 6,
    
        # Number of allpass filters - add diffusion and prevent flutter echoes (3 is optimal)
        "num_allpass_filters": 3,
    
        # Gap between dry signal and reverb start (20-50ms = natural room, 50-100ms = large hall)
        "pre_delay_ms": 50.0,

        # L/R mic distance for enhanced stereo
        "mic_spacing_m": 0.2,
    
        # Reverb/dry balance (0.2 = 20% reverb, good for cascading to prevent over-processing)
        "wet_dry_mix": 0.2,
    
        # Per-frequency band settings (creates natural room behavior)
        "band_configs": [
            {
                # LOW FREQUENCIES: Longer decay, less absorption, more stereo spread
                "rt60": 3.2,                    # Bass sustains longer (2.0-4.0s = large space/concert hall)
                "absorption": 0.05,             # Reflective surfaces (0.0-0.1 = bright, metallic)
                "stereo_decorrelation": 0.4     # Bass spreads more (0.2-0.4 = natural width)
            },
            {
                # MID FREQUENCIES: Balanced reference settings
                "rt60": 2.5,                    # Reference decay time (2.0-4.0s = large space/concert hall)
                "absorption": 0.1,              # Balanced absorption (0.1-0.3 = balanced, natural)
                "stereo_decorrelation": 0.3     # Natural stereo width (0.2-0.4 = natural width)
            },
            {
                # HIGH FREQUENCIES: Shorter decay, high absorption, focused stereo
                "rt60": 1.3,                    # Highs decay rapidly (1.0-2.0s = natural room sound)
                "absorption": 0.35,             # High frequencies absorbed quickly (0.3-0.6 = warm, soft)
                "stereo_decorrelation": 0.2     # Highs are more directional (0.2-0.4 = natural width)
            }
        ],
    
        # Default fallback settings if bands don't have specific configs
        "default_band_config": {
            "rt60": 2.5,
            "absorption": 0.1,
            "stereo_decorrelation": 0.3
        }
    },
    "base_stereo_width": {
        "parallel_forEach.use_processes": False,
    },
    "base_stereo_phase": {
        "parallel_forEach.use_processes": True,
    
        "fft_size": 1024,
        "overlap": 0.5,
    },
    "base_stereo_correlation": {
        "parallel_forEach.use_processes": False,
    },
    "base_sparkle": {
        "parallel_forEach.use_processes": False,
        
        "frame_ms": 20,
        "min_frequency_hz": 1300,
    },
    "base_freq_response": {
        "parallel_forEach.use_processes": False,
        
        "fft_size": 4096,
        "overlap": 0.5,
    },
    "base_dynamics": {
        "parallel_forEach.use_processes": False,
        
        "frame_ms": 100,
    },
    "base_dynamics_fullspectrum": {
        "parallel_forEach.use_processes": False,
        
        "frame_ms": 100,
    },
    "base_harmonics": {
        "parallel_forEach.use_processes": True,
        
        "fft_size": 8192,
        "hop_size": 4096, 
    },
    "base_harmonics_fullspectrum": {
        "parallel_forEach.use_processes": False,
        
        "fft_size": 4096,
        "hop_size": 2048, 
        "band_limit_hz": 21000,
    },
    "base_quantization": {
        "parallel_forEach.use_processes": True,
        
        "frame_size": 1024,
        "bit_depth_tolerance": 1e-6,
    },
    "base_quantization_fullspectrum": {
        "parallel_forEach.use_processes": True,
        
        "frame_size": 1024,
        "bit_depth_tolerance": 1e-6,
    },
    "image_fingerprint": {
        "parallel_forEach.use_processes": True,
        "image_types": None,    # default to all image rendering
    },
}
