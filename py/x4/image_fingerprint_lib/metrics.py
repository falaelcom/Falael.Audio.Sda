import numpy as np

METRICS = {
#    "stereo_width::width_ratio": split into "stereo_width::presence" + "stereo_width::quality" for better visualization
    "stereo_width::presence": {
        "title": "st.presence",
        "type": "unipolar",
        "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0)
    },
    "stereo_width::quality": {
        "title": "st.natrl",
        "type": "bipolar",
        "normalize_func": lambda x, config: np.clip(x, -1.0, 1.0)
    },
    "stereo_correlation::correlation": {
        "title": "st.corr",
        "type": "bipolar", 
        "normalize_func": lambda x, config: np.clip(x, -1.0, 1.0)
    },
    "stereo_phase::coherence": {
        "title": "st.phase", 
        "type": "bipolar",
        "normalize_func": lambda x, config: np.clip(x, -1.0, 1.0) 
    },

    "sparkle::sparkle": {
        "title": "sparkle",
        "type": "unipolar",
        "linear_max": 0.95,
        "transition_point": 0.3,
        "normalize_func": lambda x, config: (
            (x / config["transition_point"]) * config["linear_max"] if x <= config["transition_point"]
            else config["linear_max"] + (1 - config["linear_max"]) * (1 - np.exp(-2.0 * (x - config["transition_point"]) / config["transition_point"]))
        )
    },
    "harmonics::spectral_centroid_fraction": {
        "title": "brightness",
        "type": "unipolar",
        "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0)
    },
    "harmonics::spectral_rolloff_fraction": {
        "title": "fullness",
        "type": "unipolar",
        "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0)
    },
    "freq_response::avg_magnitude_db": {
        "title": "energy",
        "type": "bipolar",
        "neutral_point": -3.0,
        "low_extreme": -30.0,
        "high_extreme": 10.0,
        "target_range": 0.95,
        "normalize_func": lambda x, config: (
            config["target_range"] * (2 / (1 + np.exp(-((x - config["neutral_point"]) / 
            ((config["high_extreme"] - config["low_extreme"]) / 
            (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
        )
    },

    "audio_quality::overall_spectral_flatness_ratio": {
       "title": "ovrl.mus",
       "type": "bipolar",
       "musical_center": 0.4,          # Center of musical sweet spot
       "sweet_spot_width": 0.2,        # Width of good range (0.3-0.5)
       "extreme_penalty": 0.6,         # How far to extremes before max penalty
       "target_range": 0.95,
       "normalize_func": lambda x, config: (
           # Distance from musical center
           (lambda distance: (
               # If within sweet spot, positive values
               config["target_range"] * (1 - distance / (config["sweet_spot_width"] / 2))
               if distance <= config["sweet_spot_width"] / 2
               # If outside sweet spot, negative values
               else -config["target_range"] * min(1.0, (distance - config["sweet_spot_width"] / 2) / config["extreme_penalty"])
           ))(abs(x - config["musical_center"]))
       )
    },
    "audio_quality::std_overall_spectral_flatness_ratio": {
        "title": "ovrl.var",
        "type": "unipolar",
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
    "dynamic_range::overall_avg_crest_factor_db": {
        "title": "ovrl.dyn",
        "type": "bipolar",
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
    "dynamic_range::overall_std_crest_factor_db": {
       "title": "ovrl.dyn.var",
       "type": "bipolar",
        "neutral_point": 2.0,
        "low_extreme": 0.0,
        "high_extreme": 4.0,
       "target_range": 0.95,
       "normalize_func": lambda x, config: (
           1.9 * (1 / (1 + np.exp(-1.2 * (x - config["neutral_point"]))) - 0.5)
       )
    },

    "audio_quality::quantization_efficiency": {
       "title": "dither.effy",
       "type": "unipolar",
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
    "quantization::avg_spectral_slope_db": {
        "title": "dither Q",
        "type": "bipolar",
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
    "quantization::std_spectral_slope_db": {
        "title": "dither st.",
        "type": "unipolar",
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
    "quantization::unique_levels": {
        "title": "digit.res",
        "type": "unipolar",
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
    "quantization::estimated_bits": {
        "title": "bit depth",
        "type": "unipolar",
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
