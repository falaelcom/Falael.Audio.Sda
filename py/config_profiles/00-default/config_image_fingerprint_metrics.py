import numpy as np

from zulu.normalization import compound_sigmoid

CONFIG = {
    "image_fingerprint.METRIC_KEYS_RENDER": {
        "base_stereo_width::presence": True,
        "base_stereo_width::width_ratio": True,
        "base_stereo_correlation::correlation": True,
        "base_stereo_phase::coherence": True,

        "base_sparkle::sparkle": True,
        "base_harmonics::spectral_centroid_fraction": True,
        "base_harmonics::spectral_rolloff_fraction": True,
        "base_freq_response::avg_magnitude_db": True,

        "calc_audio_quality::overall_spectral_flatness_ratio": True,
        "calc_audio_quality::std_overall_spectral_flatness_ratio": True,
        "calc_dynamic_range::overall_avg_crest_factor_db": True,
        "calc_dynamic_range::overall_std_crest_factor_db": True,

        "calc_audio_quality::quantization_efficiency": True,
        "base_quantization::avg_spectral_slope_db": True,
        "base_quantization::std_spectral_slope_db": True,
        "base_quantization::unique_levels": True,

        "base_quantization::estimated_bits": True,
        "base_harmonics::spectral_flatness_ratio_pinkns_norm": True,
        "base_harmonics::std_spectral_flatness_ratio_pinkns_norm": False,
        "base_freq_response::avg_magnitude_db_pinkns_norm": True,
    },
    "image_fingerprint.METRICS_ALL": {
        "base_stereo_width::presence": {
            "title": "st.presence",
            "polarity": "unipolar",
            "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0)
        },
        "base_stereo_width::width_ratio": {
            "title": "mono-stereo",
            "polarity": "tripolar",
            "neutral_point": 0.5,
            "low_extreme": 0.0001,  # near mono, left color on chart
            "high_extreme": 1.3,    # streo breakdown, right color on chart
            "target_range": 0.99,
            "normalize_func": lambda x, config: -compound_sigmoid(x, 
                                                                x0=config["neutral_point"],
                                                                xmin_range=config["low_extreme"],
                                                                ymin_range=-config["target_range"],
                                                                xmax_range=config["high_extreme"],
                                                                ymax_range=config["target_range"])
        },
        "base_stereo_correlation::correlation": {
            "title": "st.corr",
            "polarity": "bipolar", 
            "normalize_func": lambda x, config: np.clip(x, -1.0, 1.0)
        },
        "base_stereo_phase::coherence": {
            "title": "st.phase", 
            "polarity": "bipolar",
            "normalize_func": lambda x, config: np.clip(x, -1.0, 1.0) 
        },
        "base_sparkle::sparkle": {
            "title": "base_sparkle",
            "polarity": "unipolar",
            "linear_max": 0.95,
            "transition_point": 0.3,
            "normalize_func": lambda x, config: (
                (x / config["transition_point"]) * config["linear_max"] if x <= config["transition_point"]
                else config["linear_max"] + (1 - config["linear_max"]) * (1 - np.exp(-2.0 * (x - config["transition_point"]) / config["transition_point"]))
            )
        },
        "base_harmonics::spectral_centroid_fraction": {
            "title": "low-high centroid",
            "polarity": "tripolar",
            "neutral_point": 0.5,
            "low_extreme": 0.0001,     # low freq bias, left color on chart
            "high_extreme": 0.9999,    # high freq bias, right color on chart
            "target_range": 0.99,
            "normalize_func": lambda x, config: -compound_sigmoid(x, 
                                                                x0=config["neutral_point"],
                                                                xmin_range=config["low_extreme"],
                                                                ymin_range=-config["target_range"],
                                                                xmax_range=config["high_extreme"],
                                                                ymax_range=config["target_range"])
        },
        "base_harmonics::spectral_rolloff_fraction": {
            "title": "skewd-broad rolloff",
            "polarity": "tripolar",
            "neutral_point": 0.5,
            "low_extreme": 0.0001,     # skewed freq energy distribution in band, left color on chart
            "high_extreme": 0.9999,    # broad uniform freq energy distribution in band, right color on chart
            "target_range": 0.99,
            "normalize_func": lambda x, config: -compound_sigmoid(x, 
                                                                x0=config["neutral_point"],
                                                                xmin_range=config["low_extreme"],
                                                                ymin_range=-config["target_range"],
                                                                xmax_range=config["high_extreme"],
                                                                ymax_range=config["target_range"])
        },
        "base_harmonics::spectral_flatness_ratio_pinkns_norm": {
            "title": "tonal-noise",
            "polarity": "tripolar",
            "neutral_point": 0.8,
            "low_extreme": 0.1,     # overly tonal, close to pure sinusoid, left on chart
            "high_extreme": 0.95,   # overly noist, close to pure noise, right on chart
            "target_range": 0.99,
            "normalize_func": lambda x, config: -compound_sigmoid(x, 
                                                                x0=config["neutral_point"],
                                                                xmin_range=config["low_extreme"],
                                                                ymin_range=-config["target_range"],
                                                                xmax_range=config["high_extreme"],
                                                                ymax_range=config["target_range"])
        },
        "base_harmonics::std_spectral_flatness_ratio_pinkns_norm": {
            "title": "mus.var",
            "polarity": "unipolar",
            "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0)
        },

        "base_freq_response::avg_magnitude_db": {
            "title": "energy",
            "polarity": "bipolar",
            "neutral_point": 0,
            "low_extreme": -50.0,
            "high_extreme": 50.0,
            "target_range": 0.99,
            "normalize_func": lambda x, config: compound_sigmoid(x, 
                                                                 x0 = config["neutral_point"],
                                                                 xmin_range = config["low_extreme"],
                                                                 ymin_range = -config["target_range"],
                                                                 xmax_range = config["high_extreme"],
                                                                 ymax_range = config["target_range"]
                                                                 )
        },
        "base_freq_response::avg_magnitude_db_pinkns_norm": {
            "title": "sparce-dense nrgy",
            "polarity": "bipolar",
            "neutral_point": 0,
            "low_extreme": -60.0,   # very low energy (sparse band), right on the chart
            "high_extreme": 60.0,   # very high energy (dense band), left on the chart
            "target_range": 0.99,
            "normalize_func": lambda x, config: compound_sigmoid(x, 
                                                                 x0 = config["neutral_point"],
                                                                 xmin_range = config["low_extreme"],
                                                                 ymin_range = -config["target_range"],
                                                                 xmax_range = config["high_extreme"],
                                                                 ymax_range = config["target_range"]
                                                                 )
        },

        "calc_audio_quality::overall_spectral_flatness_ratio": {
            "title": "ovrl.mus",
            "polarity": "bipolar",
            "neutral_point": 0.2,  # Shifted for 21 kHz music flatness
            "low_extreme": 0.025,  # Covers very tonal spectra
            "high_extreme": 0.5,
            "target_range": 0.999,
            "normalize_func": lambda x, config: compound_sigmoid(x, 
                                                                 x0 = config["neutral_point"],
                                                                 xmin_range = config["low_extreme"],
                                                                 ymin_range = -config["target_range"],
                                                                 xmax_range = config["high_extreme"],
                                                                 ymax_range = config["target_range"]
                                                                 )
        },
        "calc_audio_quality::std_overall_spectral_flatness_ratio": {
            "title": "ovrl.var",
            "polarity": "unipolar",
            "excellent_threshold": 0.0,     # Perfect consistency  
            "poor_threshold": 0.25,         # Excessive variation (practical max)
            "target_min": 0.05,             # Normalized value for poor
            "target_max": 0.95,             # Normalized value for excellent
            "normalize_func": lambda x, config: (
                config["target_max"] - (config["target_max"] - config["target_min"]) * 
                (1 / (1 + np.exp(-((x - (config["excellent_threshold"] + config["poor_threshold"]) / 2) / 
                ((config["poor_threshold"] - config["excellent_threshold"]) / 
                (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
            )
        },
        "calc_dynamic_range::overall_avg_crest_factor_db": {
            "title": "ovrl.dyn",
            "polarity": "bipolar",
            "neutral_point": 8.0,           # Below this = problematic compression
            "low_extreme": 3.0,             # Heavily compressed (red)
            "high_extreme": 16.0,           # Natural dynamics (green)
            "target_range": 0.95,
            "normalize_func": lambda x, config: (
                config["target_range"] * (2 / (1 + np.exp(-((x - config["neutral_point"]) / 
                ((config["high_extreme"] - config["low_extreme"]) / 
                (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
            )
        },
        "calc_dynamic_range::overall_std_crest_factor_db": {
           "title": "ovrl.dyn.var",
           "polarity": "bipolar",
            "neutral_point": 2.0,
            "low_extreme": 0.0,
            "high_extreme": 4.0,
           "target_range": 0.95,
           "normalize_func": lambda x, config: (
               1.9 * (1 / (1 + np.exp(-1.2 * (x - config["neutral_point"]))) - 0.5)
           )
        },

        "calc_audio_quality::quantization_efficiency": {
           "title": "dither.effy",
           "polarity": "unipolar",
           "optimal_point": 0.575,         # Perfect processing
           "poor_threshold": 0.25,         # Below this = 0
           "suspicious_threshold": 0.85,   # Above this = 0
           "normalize_func": lambda x, config: (
               0.0 if x <= config["poor_threshold"] or x >= config["suspicious_threshold"]
               else (
                   # Left slope: linear from 0.25 to 0.575
                   (x - config["poor_threshold"]) / (config["optimal_point"] - config["poor_threshold"])
                   if x < config["optimal_point"]
                   # Right slope: linear from 0.575 to 0.85  
                   else (config["suspicious_threshold"] - x) / (config["suspicious_threshold"] - config["optimal_point"])
               )
           )
        },
        "base_quantization::avg_spectral_slope_db": {
            "title": "dither Q",
            "polarity": "bipolar",
            "good_slope": -20.0,         # Natural rolloff (good)
            "neutral_slope": -5.0,       # Moderate rolloff
            "poor_slope": 10.0,          # Flat or boosted highs (poor)
            "target_range": 0.95,
            "normalize_func": lambda x, config: (
                config["target_range"] * (2 / (1 + np.exp(-((x - config["neutral_slope"]) / 
                ((config["poor_slope"] - config["good_slope"]) / 
                (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
            )
        },
        "base_quantization::std_spectral_slope_db": {
            "title": "dither st.",
            "polarity": "unipolar",
            "excellent_threshold": 0.0,     # Perfect consistency
            "poor_threshold": 15.0,         # High variability
            "target_min": 0.05,             # Normalized value for poor
            "target_max": 0.95,             # Normalized value for excellent
            "normalize_func": lambda x, config: (
                config["target_max"] - (config["target_max"] - config["target_min"]) * 
                (1 / (1 + np.exp(-((x - (config["excellent_threshold"] + config["poor_threshold"]) / 2) / 
                ((config["poor_threshold"] - config["excellent_threshold"]) / 
                (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
            )
        },
        "base_quantization::unique_levels": {
            "title": "digit.res",
            "polarity": "unipolar",
            "min_levels": 100,      # Poor quality threshold
            "max_levels": 100000,   # Excellent quality threshold  
            "target_max": 0.95,     # Max normalized value
            "normalize_func": lambda x, config: (
                0.0 if x <= config["min_levels"] else
                min(config["target_max"], 
                    config["target_max"] * np.log10(x / config["min_levels"]) / 
                    np.log10(config["max_levels"] / config["min_levels"]))
            )
        },

        "base_quantization::estimated_bits": {
            "title": "bit depth",
            "polarity": "unipolar",
            "poor_quality": 6.0,      # Very poor (6-bit effective)
            "excellent_quality": 24.0, # Excellent (24-bit effective)
            "target_min": 0.05,
            "target_max": 0.95,
            "normalize_func": lambda x, config: (
                config["target_min"] + (config["target_max"] - config["target_min"]) *
                (1 / (1 + np.exp(-((x - (config["poor_quality"] + config["excellent_quality"]) / 2) /
                ((config["excellent_quality"] - config["poor_quality"]) /
                (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
            )
        },
    }
}