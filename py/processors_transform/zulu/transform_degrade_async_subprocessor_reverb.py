import numpy as np
from scipy.signal import fftconvolve

from zulu.bandpass_filter import bandpass

class ReverbSubprocessor:
    """
    Reverb subprocessor for audio degradation simulation.
    Handles multiband reverb processing with FFT-based bandpass filtering.
    """
    
    def __init__(self, ctx: dict):
        """Initialize reverb subprocessor with context parameters."""
        self.log_edges = ctx['log_edges']
        self.band_configs = ctx['band_configs']
        self.room_width = ctx['room_width']
        self.room_height = ctx['room_height']
        self.room_depth = ctx['room_depth']
        self.num_comb_filters = ctx['num_comb_filters']
        self.num_allpass_filters = ctx['num_allpass_filters']
        self.pre_delay_ms = ctx['pre_delay_ms']
        self.wet_dry_mix = ctx['wet_dry_mix']
        self.mic_spacing_m = ctx['mic_spacing_m']
    
    def process(self, chunk_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Process a chunk with reverb.
        
        Args:
            chunk_data: Stereo audio chunk [samples, 2]
            sample_rate: Audio sample rate
            
        Returns:
            Processed stereo audio chunk
        """
        left_channel = chunk_data[:, 0]
        right_channel = chunk_data[:, 1]
        
        bands = len(self.log_edges) - 1
        
        # If only 1 band, skip multiband processing entirely
        if bands == 1:
            # Direct reverb application without bandpass filtering
            left_reverb, right_reverb = self._apply_reverb_fft(
                left_channel, 
                right_channel, 
                sample_rate, 
                self.band_configs[0]
            )
            return np.column_stack((left_reverb, right_reverb))
        
        # Initialize output channels for multiband processing
        left_output = np.zeros_like(left_channel)
        right_output = np.zeros_like(right_channel)
        
        # Process each frequency band
        for band_idx in range(bands):
            f_low = self.log_edges[band_idx]
            f_high = self.log_edges[band_idx + 1]
            band_config = self.band_configs[band_idx]
            
            # FFT-based bandpass filter for this frequency range
            left_band = bandpass(left_channel, sample_rate, f_low, f_high, )
            right_band = bandpass(right_channel, sample_rate, f_low, f_high)
            
            # Apply reverb to this band
            left_reverb, right_reverb = self._apply_reverb_fft(
                left_band, 
                right_band, 
                sample_rate, 
                band_config
            )
            
            # Add processed band to output
            left_output += left_reverb
            right_output += right_reverb
        
        # Optional: Apply a small compensation factor if energy is lost in multiband processing
        original_rms = np.sqrt(np.mean(left_channel**2 + right_channel**2))
        output_rms = np.sqrt(np.mean(left_output**2 + right_output**2))
        
        compensation_applied = 1.0
        if output_rms > 0 and original_rms > 0:
            # Only apply gentle compensation if significant energy loss
            energy_ratio = original_rms / output_rms
            if energy_ratio > 1.5:  # Only if we lost more than 50% energy
                compensation = min(energy_ratio, 2.0)  # Cap at 2x
                left_output *= compensation
                right_output *= compensation
                compensation_applied = compensation
        
        # Combine channels
        return np.column_stack((left_output, right_output))
    
    def _apply_reverb_fft(self, left_band: np.ndarray, right_band: np.ndarray, sample_rate: int, band_config: dict) -> tuple:
        """
        FFT-based Schroeder reverb implementation with automatic gain compensation.
        """
        
        # Extract band-specific config
        rt60 = band_config.get("rt60", 2.5)
        absorption = band_config.get("absorption", 0.1)
        stereo_decorrelation = band_config.get("stereo_decorrelation", 0.3)
        
        # CRITICAL: Calculate original signal energy BEFORE processing
        original_left_rms = np.sqrt(np.mean(left_band**2)) if len(left_band) > 0 else 0.0
        original_right_rms = np.sqrt(np.mean(right_band**2)) if len(right_band) > 0 else 0.0
        original_total_rms = np.sqrt((original_left_rms**2 + original_right_rms**2) / 2.0)
        
        # Generate impulse responses for left and right channels
        ir_left = self._generate_impulse_response(sample_rate, rt60, absorption, 
                                                 stereo_decorrelation, channel='left')
        
        ir_right = self._generate_impulse_response(sample_rate, rt60, absorption,
                                                  stereo_decorrelation, channel='right')
        
        # Apply convolution
        left_reverb_full = fftconvolve(left_band, ir_left, mode='full')
        right_reverb_full = fftconvolve(right_band, ir_right, mode='full')
        
        # Trim to original length (reverb tail truncation)
        left_reverb = left_reverb_full[:len(left_band)]
        right_reverb = right_reverb_full[:len(right_band)]
        
        # CRITICAL: Energy-compensated wet/dry mixing
        # Equal-power crossfade maintains energy regardless of wet_dry_mix
        dry_gain = np.sqrt(1.0 - self.wet_dry_mix)  # Equal power law
        wet_gain = np.sqrt(self.wet_dry_mix)
        
        left_output = dry_gain * left_band + wet_gain * left_reverb
        right_output = dry_gain * right_band + wet_gain * right_reverb
        
        # CRITICAL: Automatic gain compensation to maintain original level
        compensation_gain = 1.0
        if original_total_rms > 0:
            # Calculate output energy
            output_left_rms = np.sqrt(np.mean(left_output**2)) if len(left_output) > 0 else 0.0
            output_right_rms = np.sqrt(np.mean(right_output**2)) if len(right_output) > 0 else 0.0
            output_total_rms = np.sqrt((output_left_rms**2 + output_right_rms**2) / 2.0)
            
            if output_total_rms > 0:
                # Calculate compensation gain to match original level
                compensation_gain = original_total_rms / output_total_rms
                
                # Apply safety limiting to prevent excessive boosting  
                compensation_gain = min(compensation_gain, 4.0)  # Max 12dB boost
                compensation_gain = max(compensation_gain, 0.25) # Min -12dB reduction
                
                # Apply compensation
                left_output *= compensation_gain
                right_output *= compensation_gain
        
        return left_output, right_output
    
    def _generate_impulse_response(self, sample_rate: int, rt60: float, absorption: float,
                                  stereo_decorrelation: float, channel: str) -> np.ndarray:
        """
        Generate impulse response for Schroeder reverb.
        """
        # Make IR longer to capture full decay
        ir_length_sec = max(rt60 * 3.0, 3.0)
        ir_length_samples = int(ir_length_sec * sample_rate)
        
        # Speed of sound in air (m/s)
        speed_of_sound = 343.0
        
        # Calculate delay times
        delay_width = self.room_width / speed_of_sound
        delay_height = self.room_height / speed_of_sound  
        delay_depth = self.room_depth / speed_of_sound
        
        base_delays = [delay_width, delay_height, delay_depth]
        
        # More varied comb delays with prime number ratios
        comb_delays = []
        prime_ratios = [1.0, 1.17, 1.31, 1.43, 1.61, 1.73, 1.91, 2.03]
        
        for i in range(self.num_comb_filters):
            base_idx = i % len(base_delays)
            ratio_idx = i % len(prime_ratios)
            variation = prime_ratios[ratio_idx]
            delay_time = base_delays[base_idx] * variation
            comb_delays.append(delay_time)
        
        # Apply stereo decorrelation and microphone positioning
        if channel == 'right':
            # Stereo decorrelation (original approach)
            for i in range(len(comb_delays)):
                decorr_offset = stereo_decorrelation * 0.03 * (i + 1) / sample_rate
                comb_delays[i] += decorr_offset
            
            # Microphone positioning offset
            # Right microphone is slightly further from left-side sound sources
            mic_delay_offset = self.mic_spacing_m / (2 * speed_of_sound)  # ~0.3ms for 20cm spacing
            for i in range(len(comb_delays)):
                comb_delays[i] += mic_delay_offset
        
        # Convert to samples
        comb_delay_samples = [int(delay * sample_rate) for delay in comb_delays]
        pre_delay_samples = int((self.pre_delay_ms / 1000.0) * sample_rate)
        
        # Calculate feedback gains
        comb_gains = []
        for delay_samples in comb_delay_samples:
            if delay_samples > 0:
                delay_time = delay_samples / sample_rate
                gain = 10 ** (-3 * delay_time / rt60)
                gain *= (1.0 - absorption)
                gain = min(gain, 0.98)
                comb_gains.append(gain)
            else:
                comb_gains.append(0.0)
        
        # Generate allpass delays with more variation
        allpass_delays = []
        for i in range(self.num_allpass_filters):
            delay_time = delay_width * (0.15 + i * 0.08)
            allpass_delays.append(int(delay_time * sample_rate))
        
        allpass_gains = [0.7] * self.num_allpass_filters
        
        # Create impulse response by exciting the filter network
        impulse = np.zeros(ir_length_samples)
        if pre_delay_samples < len(impulse):
            impulse[pre_delay_samples] = 1.0  # Unit impulse after pre-delay
        
        # Apply comb filters (parallel)
        comb_output = np.zeros(ir_length_samples)
        
        for i, (delay_samples, gain) in enumerate(zip(comb_delay_samples, comb_gains)):
            if delay_samples > 0 and delay_samples < ir_length_samples:
                # Create single comb filter response
                comb_ir = self._create_comb_filter_ir(ir_length_samples, delay_samples, gain)
                # Convolve impulse with this comb filter
                comb_response = fftconvolve(impulse, comb_ir, mode='full')
                # Trim to original length
                comb_response = comb_response[:ir_length_samples]
                comb_output += comb_response
        
        # Normalize comb output to prevent buildup
        if self.num_comb_filters > 0:
            comb_output /= np.sqrt(self.num_comb_filters)  # Energy-preserving normalization
        
        # Apply allpass filters (series)
        allpass_output = comb_output.copy()
        
        for delay_samples, gain in zip(allpass_delays, allpass_gains):
            if delay_samples > 0 and delay_samples < len(allpass_output):
                allpass_ir = self._create_allpass_filter_ir(ir_length_samples, delay_samples, gain)
                # Apply allpass filter
                allpass_temp = fftconvolve(allpass_output, allpass_ir, mode='full')
                allpass_output = allpass_temp[:ir_length_samples]
        
        # Normalize to preserve energy and prevent clipping
        if np.max(np.abs(allpass_output)) > 0:
            # Scale to maintain reasonable level
            max_val = np.max(np.abs(allpass_output))
            if max_val > 0.5:  # Prevent clipping
                allpass_output /= (max_val * 2.0)
        
        return allpass_output
    
    def _create_comb_filter_ir(self, length: int, delay_samples: int, gain: float) -> np.ndarray:
        """
        Create impulse response for a single comb filter.
        """
        ir = np.zeros(length)
        if delay_samples < length:
            ir[0] = 1.0  # Direct signal
            
            # Add feedback taps
            pos = delay_samples
            current_gain = gain
            
            while pos < length and current_gain > 0.001:  # Stop when gain becomes negligible
                ir[pos] += current_gain
                pos += delay_samples
                current_gain *= gain
        
        return ir
    
    def _create_allpass_filter_ir(self, length: int, delay_samples: int, gain: float) -> np.ndarray:
        """
        Create impulse response for a single allpass filter.
        """
        ir = np.zeros(length)
        if delay_samples < length:
            ir[0] = -gain  # Feedforward term
            ir[delay_samples] = 1.0  # Delayed signal
            
            # The feedback creates an infinite series, but we approximate with a few terms
            pos = delay_samples
            current_gain = gain
            for _ in range(20):  # More iterations for better approximation
                if pos < length:
                    ir[pos] += current_gain
                    pos += delay_samples
                    current_gain *= gain * gain
                else:
                    break
        
        return ir