CONFIG = {
    "transform_degrade": {
    
        "reverb_enabled": True,
        "signal_noise_enabled": True,

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
    
        # Professional studio live room dimensions (control room + live room combined)
        "room_width": 8.0,     # Typical studio width (~23ms delay, ~43Hz resonance)
        "room_height": 3.5,    # Standard ceiling height (~10ms delay, ~98Hz resonance)  
        "room_depth": 12.0,    # Live room depth (~35ms delay, ~29Hz resonance)
    
        # Six comb filters for smooth, non-metallic character without flutter
        "num_comb_filters": 6,
    
        # Three allpass stages for optimal diffusion and echo prevention
        "num_allpass_filters": 3,
    
        # Close-mic studio feel with minimal early reflection gap
        "pre_delay_ms": 25.0,
    
        # L/R mic distance for enhanced stereo
        "mic_spacing_m": 0.2,

        # slight mix
        "wet_dry_mix": 0.2,
        #"wet_dry_mix": 0,
    
        # Studio-tuned frequency response: controlled but not dead
        "band_configs": [
            {
                # LOW FREQUENCIES: Controlled bass with subtle room support
                "rt60": 1.8,                    # Moderate bass sustain (studio live room character)
                "absorption": 0.15,             # Bass trapping simulation (studio treatment)
                "stereo_decorrelation": 0.3     # Controlled low-end spread
            },
            {
                # MID FREQUENCIES: Tight, punchy studio sound
                "rt60": 1.2,                    # Quick mid decay (typical studio live room)
                "absorption": 0.25,             # Moderate acoustic treatment absorption
                "stereo_decorrelation": 0.25    # Focused but natural stereo image
            },
            {
                # HIGH FREQUENCIES: Crisp, detailed high-end
                "rt60": 0.8,                    # Rapid high decay (heavy studio treatment)
                "absorption": 0.5,              # Strong high-frequency absorption (foam/panels)
                "stereo_decorrelation": 0.15    # Precise high-frequency imaging
            }
        ],
    
        # Fallback settings matching mid-frequency studio characteristics
        "default_band_config": {
            "rt60": 1.2,
            "absorption": 0.25,
            "stereo_decorrelation": 0.25
        },

        "signal_noise_config": {
           "noise_gain": 0.01,                    # Base noise level
           "envelope_follow_rate": 0.95,          # How closely to follow envelope (0-1)
           "attack_time_ms": 5.0,                 # Envelope follower attack
           "release_time_ms": 20.0,               # Envelope follower release
           "noise_color": "white",                # 'white', 'pink', 'brown'
           "base_stereo_correlation": 0.7,             # L/R correlation (0=independent, 1=mono)
           "spectral_sensitivity": 0.0,           # Scale by spectral density
           "complexity_sensitivity": 0.0          # Scale by spectral complexity
        },
    },
}