CONFIG = {
    "image_fingerprint.METRIC_KEYS_RENDER": {

        "base_stereo_width::width_ratio": True,
        "base_stereo_correlation::correlation": True,
        "base_stereo_phase::coherence": True,

        "base_harmonics::spectral_flatness_ratio_pinkns_norm": False,
        "base_harmonics::spectral_centroid_fraction": False,
        "base_harmonics::std_spectral_flatness_ratio_pinkns_norm": False,

        "base_freq_response::avg_magnitude_db_pinkns_norm": False,
        "base_sparkle::sparkle": False,
        "calc_dynamic_range::overall_avg_crest_factor_db": False,
        "calc_audio_quality::quantization_efficiency": False,
        "base_quantization::avg_spectral_slope_db": False,
        "base_quantization::unique_levels": False,
        "base_quantization::estimated_bits": False,
        "base_stereo_width::presence": False,
        "calc_audio_quality::std_overall_spectral_flatness_ratio": False,
        "base_quantization::std_spectral_slope_db": False,
        "calc_dynamic_range::overall_std_crest_factor_db": False,
        "base_freq_response::avg_magnitude_db": False,   # disabled in favor of "base_freq_response::avg_magnitude_db_pinkns_norm"
        "calc_audio_quality::overall_spectral_flatness_ratio": False, # disabled in favor of "base_harmonics::spectral_flatness_ratio_pinkns_norm"
        "base_harmonics::spectral_rolloff_fraction": False, # mimics "base_harmonics::spectral_centroid_fraction"
    },
}