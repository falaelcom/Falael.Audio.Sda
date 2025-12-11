CONFIG = {
    "transform_stereo_width_fullspectrum_fulltrack":
    {
        # for desmos.com - y=\frac{e^{\left(\frac{ax}{x_{1}}\right)}-1}{e^{a}-1}

        #"correction_fn": "linear",  # "linear" or "exponential"
        "correction_fn": "linear",  # "linear" or "exponential"
        "vertical_translation": 0,
        "x_1": 0.75,           # "exponential" only
        "flatness": 4.5,    # "exponential" only
        "slope": 0.4,       # "linear" only
        "min_freq_hz": 160,
        "max_freq_hz": 21000,
        "bell_curve_decay_speed": 2.9,
        "window_samples": 4096,
        "hop_samples": 2048,
        "window_type": "hann",
    },
}
