import numpy as np

METRICS = {
    "audio_quality::avg_sinad_db": {
        "title": "SINAD",
        "type": "unipolar",
        "excellent_threshold": 70.0,    # High-end audio
        "poor_threshold": 40.0,         # Poor quality threshold  
        "target_min": 0.05,
        "target_max": 0.95,
        "normalize_func": lambda x, config: (
            config["target_min"] + (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["excellent_threshold"] + config["poor_threshold"]) / 2) / 
            ((config["excellent_threshold"] - config["poor_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
    "audio_quality::std_sinad_db": {
        "title": "SINAD.stab",
        "type": "bipolar", 
        "neutral_point": 8.0,          # Audible problems start at 8dB
        "low_extreme": 0.0,            # Perfect stability
        "high_extreme": 16.0,          # Very poor stability
        "target_range": 0.95,
        "normalize_func": lambda x, config: (
            config["target_range"] * (2 / (1 + np.exp(-((config["neutral_point"] - x) / 
            ((config["high_extreme"] - config["low_extreme"]) / 
            (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
        )
    },
    "audio_quality::spectral_flatness_ratio": {
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
   "harmonics::richness_db": {
        "title": "mus.rich",
        "type": "unipolar",
        "flat_threshold": 0.0,          # Flat/boring sound
        "rich_threshold": 100.0,         # Rich musical content
        "target_min": 0.05,             # Normalized value for flat
        "target_max": 0.95,             # Normalized value for rich
        "normalize_func": lambda x, config: (
            config["target_min"] + (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["flat_threshold"] + config["rich_threshold"]) / 2) / 
            ((config["rich_threshold"] - config["flat_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
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
        "type": "unipolar",
        "normalize_func": lambda x, config: np.clip(x, 0.0, 1.0) 
    },
    "quantization::avg_noise_floor_db": {
        "title": "noise Q",
        "type": "unipolar",
        "excellent_threshold": -200.0,  # Maps to target_max
        "poor_threshold": -20.0,        # Maps to target_min
        "target_min": 0.05,             # Normalized value for poor quality
        "target_max": 0.95,             # Normalized value for excellent quality
        "normalize_func": lambda x, config: (
            config["target_max"] - (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["excellent_threshold"] + config["poor_threshold"]) / 2) / 
            ((config["poor_threshold"] - config["excellent_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
    "quantization::noise_floor_std_db": {
        "title": "noise st.",
        "type": "unipolar", 
        "excellent_threshold": 0.0,     # Perfect consistency
        "poor_threshold": 20.0,         # High variability
        "target_min": 0.05,             # Normalized value for poor
        "target_max": 0.95,             # Normalized value for excellent
        "normalize_func": lambda x, config: (
            config["target_max"] - (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["excellent_threshold"] + config["poor_threshold"]) / 2) / 
            ((config["poor_threshold"] - config["excellent_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
    "quantization::dynamic_range_db": {
        "title": "dyn.rng",
        "type": "bipolar",
        "practical_min_x": 20.0, # must adapt values when changing the multiband settings
        "practical_min_y": -0.95,
        "practical_max_x": 200.0, # must adapt values when changing the multiband settings
        "practical_max_y": 0.95,
        "practical_midpoint_x": 110.0, # must adapt values when changing the multiband settings
        "normalize_func": lambda x, config: (
            # Calculate scale from config values
            (lambda scale: (
                # Lower range: x < midpoint -> y in [-0.95, 0)
                ((1 / (1 + np.exp(-(x - config["practical_midpoint_x"]) / scale)) - 0.05) / 0.45) * 0.95 - 0.95
                if x < config["practical_midpoint_x"] else
                # Upper range: x >= midpoint -> y in [0, 0.95]
                ((1 / (1 + np.exp(-(x - config["practical_midpoint_x"]) / scale)) - 0.5) / 0.45) * 0.95
            ))(50 / np.log(19))  # scale = 16.9812
        )
    },
    "dynamic_range::peak_to_noise_ratio_db": {
        "title": "dyn.PTNR",
        "type": "bipolar",
        "neutral_point": 120.0,        # Based on mid-frequency performance
        "low_extreme": 40.0,           # Poor quality (below high-freq minimum)
        "high_extreme": 200.0,         # Excellent (above observed maximum)
        "target_range": 0.95,
        "normalize_func": lambda x, config: (
            config["target_range"] * (2 / (1 + np.exp(-((x - config["neutral_point"]) / 
            ((config["high_extreme"] - config["low_extreme"]) / 
            (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
        )
    },
    "dynamic_range::signal_to_noise_ratio_db": {
        "title": "dyn.STNR",
        "type": "bipolar",
        "neutral_point": 100.0,        # Based on mid-frequency performance
        "low_extreme": 20.0,           # Poor quality (below observed minimum)
        "high_extreme": 180.0,         # Excellent (above observed maximum)
        "target_range": 0.95,
        "normalize_func": lambda x, config: (
            config["target_range"] * (2 / (1 + np.exp(-((x - config["neutral_point"]) / 
            ((config["high_extreme"] - config["low_extreme"]) / 
            (2 * np.log((1 + config["target_range"]) / (1 - config["target_range"]))))))) - 1)
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
    "dynamics::crest_factor_db": {
        "title": "dynamics",
        "type": "unipolar",
        "compressed_threshold": 3.0,    # Heavily compressed
        "natural_threshold": 20.0,      # Natural dynamics
        "target_min": 0.05,             # Normalized value for compressed
        "target_max": 0.95,             # Normalized value for natural
        "normalize_func": lambda x, config: (
            config["target_min"] + (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["compressed_threshold"] + config["natural_threshold"]) / 2) / 
            ((config["natural_threshold"] - config["compressed_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
    "dynamics::avg_crest_factor_db": {
        "title": "avg.dyn",
        "type": "unipolar",
        "compressed_threshold": 3.0,    # Heavily compressed
        "natural_threshold": 16.0,      # Natural dynamics  
        "target_min": 0.05,             # Normalized value for compressed
        "target_max": 0.95,             # Normalized value for natural
        "normalize_func": lambda x, config: (
            config["target_min"] + (config["target_max"] - config["target_min"]) * 
            (1 / (1 + np.exp(-((x - (config["compressed_threshold"] + config["natural_threshold"]) / 2) / 
            ((config["natural_threshold"] - config["compressed_threshold"]) / 
            (2 * np.log((1 - config["target_min"]) / config["target_min"])))))))
        )
    },
    "freq_response::avg_magnitude_db": {
        "title": "rel.lvl",
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
    "quantization::spectral_slope_std_db": {
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
}
