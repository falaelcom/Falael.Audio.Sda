CONFIG = {
    "transform_stereo_width_fullspectrum_fulltrack":
    {
        # for desmos.com - y=\frac{e^{\left(\frac{ax}{x_{1}}\right)}-1}{e^{a}-1}

        #"correction_fn": "linear",  # "linear" or "exponential"
        "correction_fn": "exponential",  # "linear" or "exponential"
        "vertical_translation": 0,
        "x_1": 1.8,           # "exponential" only - "How fast does it grow?" - lower values < 1 - faster rise, higher values > 1 - stays lower for longer
        "flatness": 0.75,    # "exponential" only - "How dramatically curved is it? - lower values [0..1] - closer to a line; higher values > 1 - more curved, steeper in the end"
        "slope": 0.4,       # "linear" only
        "min_freq_hz": 5,
        "max_freq_hz": 21000,
        "bell_curve_decay_speed": 2.9,
        "window_samples": 4096,
        "hop_samples": 2048,
        "window_type": "hann",
    },
}
