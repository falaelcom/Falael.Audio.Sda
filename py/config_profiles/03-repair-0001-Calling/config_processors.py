CONFIG = {
    "transform_stereo_width_fullspectrum_fulltrack":
    {
        "parallel_forEach.enable": False,

        "slope_min_y": 0.0,
        "slope": 0.6,
        "min_freq_hz": 350,
        "max_freq_hz": 10000,
        "bell_curve_decay_speed": 2.85,
        "window_samples": 4096,
        "hop_samples": 2048,
        "window_type": "hann",
    },
    "transform_stereo_phase_fullspectrum_fulltrack":
    {
        "parallel_forEach.enable": False,

        "slope_min_y": 0.0,
        "slope": 0.00000200,
        "min_freq_hz": 350,
        "max_freq_hz": 10000,
        "bell_curve_decay_speed": 2.2,
        "window_samples": 4096,
        "hop_samples": 2048,
        "window_type": "hann",
    },
}
