CONFIG = {
    "transform_degrade": {
    
        "reverb_enabled": True,
        "signal_noise_enabled": False,

        # Enable detailed reverb generation diagnostics
        "debug_mode": True,
    
        # Progressive reverb buildup - each 4-second chunk gets exponentially more complex
        "cascade_mode": True,

        # Full audio spectrum processing range
        "multiband.low_hz": 20,
        "multiband.high_hz": 21000,
    
        # Three-way frequency split for natural studio room response
        "multiband.bands": 3,

        # 4-second chunks for moderate cascade progression (longer = less frequent changes)
        "chunk_duration_sec": 15,
    
        "room_width": 1.7,    # Avoid simple ratios
        "room_height": 2.3,   # Irrational numbers break patterns
        "room_depth": 1.9,    # No harmonic relationships
    
        # Six comb filters for smooth, non-metallic character without flutter
        "num_comb_filters": 12,
    
        # Three allpass stages for optimal diffusion and echo prevention
        "num_allpass_filters": 6,
    
        # Close-mic studio feel with minimal early reflection gap
        "pre_delay_ms": 30,
    
        # L/R mic distance for enhanced stereo
        "mic_spacing_m": 0.2,

        # slight mix
        #"wet_dry_mix": 0.025,
        "wet_dry_mix": 0,
    
        # Studio-tuned frequency response: controlled but not dead
        "band_configs": [
            {
                # LOW FREQUENCIES: Controlled bass with subtle room support
                "rt60": 1.8,                    # Moderate bass sustain (studio live room character)
                "absorption": 0.8,              # Bass trapping simulation (studio treatment)
                "stereo_decorrelation": 0.5     # Controlled low-end spread
            },
            {
                # MID FREQUENCIES: Tight, punchy studio sound
                "rt60": 1.2,                    # Quick mid decay (typical studio live room)
                "absorption": 1.2,                # Moderate acoustic treatment absorption
                "stereo_decorrelation": 0.4    # Focused but natural stereo image
            },
            {
                # HIGH FREQUENCIES: Crisp, detailed high-end
                "rt60": 0.8,                    # Rapid high decay (heavy studio treatment)
                "absorption": 2.5,                # Strong high-frequency absorption (foam/panels)
                "stereo_decorrelation": 0.3    # Precise high-frequency imaging
            }
        ],
    
        # Fallback settings matching mid-frequency studio characteristics
        "default_band_config": {
            "rt60": 1.2,
            "absorption": 0.25,
            "stereo_decorrelation": 0.25
        },

        "signal_noise_config": {
           "noise_gain": 0.075,                    # Base noise level
           "envelope_follow_rate": 0.95,          # How closely to follow envelope (0-1)
           "attack_time_ms": 5.0,                 # Envelope follower attack
           "release_time_ms": 20.0,               # Envelope follower release
           "noise_color": "white",                # 'white', 'pink', 'brown'
           "base_stereo_correlation": 0.6,             # L/R correlation (0=independent, 1=mono)
           "spectral_sensitivity": 1,           # Scale by spectral density
           "complexity_sensitivity": 0          # Scale by spectral complexity
        },
    },
}