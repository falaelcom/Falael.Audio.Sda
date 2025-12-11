import numpy as np
from scipy import signal

class SignalNoiseSubprocessor:
    """
    Signal-following noise subprocessor for audio degradation simulation.
    Generates noise that follows the amplitude envelope of the input signal.
    """
    
    def __init__(self, ctx: dict):
        """Initialize signal noise subprocessor with context parameters."""
        # Extract signal noise configuration from context
        signal_noise_config = ctx.get('signal_noise_config', {})
        
        self.noise_gain = signal_noise_config.get('noise_gain', 0.01)  # Base noise level
        self.envelope_follow_rate = signal_noise_config.get('envelope_follow_rate', 0.95)  # How closely to follow envelope (0-1)
        self.attack_time_ms = signal_noise_config.get('attack_time_ms', 5.0)  # Envelope follower attack
        self.release_time_ms = signal_noise_config.get('release_time_ms', 20.0)  # Envelope follower release
        self.noise_color = signal_noise_config.get('noise_color', 'white')  # 'white', 'pink', 'brown'
        self.base_stereo_correlation = signal_noise_config.get('base_stereo_correlation', 0.7)  # L/R correlation (0=independent, 1=mono)
        
        # Content-agnostic signal characteristics
        self.spectral_sensitivity = signal_noise_config.get('spectral_sensitivity', 0.0)  # Scale by spectral density
        self.complexity_sensitivity = signal_noise_config.get('complexity_sensitivity', 0.0)  # Scale by spectral complexity
    
    def process(self, chunk_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Generate signal-following noise.
        
        Args:
            chunk_data: Stereo audio chunk [samples, 2] - the ORIGINAL signal
            sample_rate: Audio sample rate
            
        Returns:
            Generated noise that follows the signal envelope [samples, 2]
        """
        if len(chunk_data) == 0:
            return np.zeros_like(chunk_data)
        
        left_channel = chunk_data[:, 0]
        right_channel = chunk_data[:, 1]
        
        # Extract amplitude envelopes from original signal
        left_envelope = self._extract_envelope(left_channel, sample_rate)
        right_envelope = self._extract_envelope(right_channel, sample_rate)
        
        # Analyze signal characteristics for content-agnostic scaling
        left_spectral_density = self._analyze_spectral_density(left_channel, sample_rate)
        right_spectral_density = self._analyze_spectral_density(right_channel, sample_rate)
        left_spectral_complexity = self._analyze_spectral_complexity(left_channel, sample_rate)
        right_spectral_complexity = self._analyze_spectral_complexity(right_channel, sample_rate)
        
        # Calculate dynamic gain scaling based on signal characteristics
        left_gain_scale = self._calculate_gain_scaling(left_spectral_density, left_spectral_complexity)
        right_gain_scale = self._calculate_gain_scaling(right_spectral_density, right_spectral_complexity)
        
        # Generate base noise
        left_noise_raw = self._generate_colored_noise(len(left_channel), sample_rate)
        right_noise_raw = self._generate_colored_noise(len(right_channel), sample_rate)
        
        # Apply spectral matching if spectral_sensitivity > 0
        if self.spectral_sensitivity > 0:
            left_noise_raw = self._apply_spectral_matching(left_noise_raw, left_channel, sample_rate)
            right_noise_raw = self._apply_spectral_matching(right_noise_raw, right_channel, sample_rate)
        
        # Apply stereo correlation
        if self.base_stereo_correlation < 1.0:
            # Mix independent noise with correlated noise
            correlation_mix = self.base_stereo_correlation
            uncorrelated_mix = 1.0 - correlation_mix
            
            # Create correlated component (mono noise for both channels)
            mono_noise = self._generate_colored_noise(len(left_channel), sample_rate)
            
            left_noise = correlation_mix * mono_noise + uncorrelated_mix * left_noise_raw
            right_noise = correlation_mix * mono_noise + uncorrelated_mix * right_noise_raw
        else:
            # Fully correlated (mono)
            mono_noise = self._generate_colored_noise(len(left_channel), sample_rate)
            left_noise = mono_noise
            right_noise = mono_noise
        
        # Modulate noise by signal envelope and content characteristics
        left_noise_modulated = left_noise * left_envelope * self.noise_gain * left_gain_scale
        right_noise_modulated = right_noise * right_envelope * self.noise_gain * right_gain_scale
        
        return np.column_stack((left_noise_modulated, right_noise_modulated))
    
    def _extract_envelope(self, audio_signal: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Extract amplitude envelope from audio signal using envelope follower.
        """
        # Calculate attack and release coefficients
        attack_coeff = np.exp(-1.0 / (self.attack_time_ms * sample_rate / 1000.0))
        release_coeff = np.exp(-1.0 / (self.release_time_ms * sample_rate / 1000.0))
        
        # Get absolute values
        abs_signal = np.abs(audio_signal)
        
        # Envelope follower implementation
        envelope = np.zeros_like(abs_signal)
        prev_envelope = 0.0
        
        for i, sample in enumerate(abs_signal):
            if sample > prev_envelope:
                # Attack - follow quickly
                envelope[i] = attack_coeff * prev_envelope + (1.0 - attack_coeff) * sample
            else:
                # Release - follow slowly
                envelope[i] = release_coeff * prev_envelope + (1.0 - release_coeff) * sample
            
            prev_envelope = envelope[i]
        
        # Apply envelope follow rate (how closely to follow vs. constant level)
        constant_level = np.mean(envelope) if len(envelope) > 0 else 0.0
        envelope = self.envelope_follow_rate * envelope + (1.0 - self.envelope_follow_rate) * constant_level
        
        return envelope
    
    def _generate_colored_noise(self, length: int, sample_rate: int) -> np.ndarray:
        """
        Generate colored noise based on noise_color setting.
        """
        # Start with white noise
        white_noise = np.random.normal(0, 1, length)
        
        if self.noise_color == 'white':
            return white_noise
        
        elif self.noise_color == 'pink':
            # Pink noise: -3dB/octave roll-off
            # Simple approximation using moving average
            b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
            a = np.array([1, -2.494956002, 2.017265875, -0.522189400])
            return signal.lfilter(b, a, white_noise)
        
        elif self.noise_color == 'brown':
            # Brown noise: -6dB/octave roll-off
            # Integration of white noise (with leakage to prevent DC buildup)
            brown_noise = np.zeros_like(white_noise)
            integrator = 0.0
            leak_factor = 0.9999  # Prevent DC buildup
            
            for i, sample in enumerate(white_noise):
                integrator = integrator * leak_factor + sample
                brown_noise[i] = integrator
            
            return brown_noise * 0.1  # Scale down since integration increases level
        
        else:
            return white_noise
    
    def _analyze_spectral_density(self, audio_signal: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Analyze spectral density - how much frequency content is active.
        Returns time-varying spectral density measure.
        """
        if len(audio_signal) == 0:
            return np.array([1.0])
        
        # Use windowed FFT to get time-varying spectral content
        window_size = 1024
        hop_size = window_size // 4
        
        # Calculate number of windows
        num_windows = max(1, (len(audio_signal) - window_size) // hop_size + 1)
        spectral_density = np.zeros(num_windows)
        
        for i in range(num_windows):
            start = i * hop_size
            end = min(start + window_size, len(audio_signal))
            window = audio_signal[start:end]
            
            if len(window) < window_size:
                # Pad the last window
                window = np.pad(window, (0, window_size - len(window)), mode='constant')
            
            # Apply window function
            windowed = window * np.hanning(len(window))
            
            # Get magnitude spectrum
            spectrum = np.abs(np.fft.rfft(windowed))
            
            # Calculate spectral density (number of active frequency bins)
            # Normalize by peak to get relative measure
            if np.max(spectrum) > 0:
                normalized_spectrum = spectrum / np.max(spectrum)
                # Count bins above threshold (active frequencies)
                active_bins = np.sum(normalized_spectrum > 0.1)
                spectral_density[i] = active_bins / len(spectrum)
            else:
                spectral_density[i] = 0.0
        
        # Interpolate back to original signal length
        if num_windows == 1:
            return np.full(len(audio_signal), spectral_density[0])
        
        # Create time axis for interpolation
        window_times = np.arange(num_windows) * hop_size + window_size // 2
        signal_times = np.arange(len(audio_signal))
        
        return np.interp(signal_times, window_times, spectral_density)
    
    def _analyze_spectral_complexity(self, audio_signal: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Analyze spectral complexity - how spread out the spectral energy is.
        Returns time-varying complexity measure based on spectral flatness.
        """
        if len(audio_signal) == 0:
            return np.array([1.0])
        
        window_size = 1024
        hop_size = window_size // 4
        
        num_windows = max(1, (len(audio_signal) - window_size) // hop_size + 1)
        spectral_complexity = np.zeros(num_windows)
        
        for i in range(num_windows):
            start = i * hop_size
            end = min(start + window_size, len(audio_signal))
            window = audio_signal[start:end]
            
            if len(window) < window_size:
                window = np.pad(window, (0, window_size - len(window)), mode='constant')
            
            # Apply window function
            windowed = window * np.hanning(len(window))
            
            # Get magnitude spectrum
            spectrum = np.abs(np.fft.rfft(windowed))
            spectrum = spectrum[1:]  # Remove DC component
            
            # Calculate spectral flatness (geometric mean / arithmetic mean)
            if len(spectrum) > 0 and np.all(spectrum >= 0):
                # Add small epsilon to avoid log(0)
                spectrum_safe = spectrum + 1e-10
                geometric_mean = np.exp(np.mean(np.log(spectrum_safe)))
                arithmetic_mean = np.mean(spectrum)
                
                if arithmetic_mean > 0:
                    spectral_flatness = geometric_mean / arithmetic_mean
                    spectral_complexity[i] = spectral_flatness
                else:
                    spectral_complexity[i] = 0.0
            else:
                spectral_complexity[i] = 0.0
        
        # Interpolate back to original signal length
        if num_windows == 1:
            return np.full(len(audio_signal), spectral_complexity[0])
        
        window_times = np.arange(num_windows) * hop_size + window_size // 2
        signal_times = np.arange(len(audio_signal))
        
        return np.interp(signal_times, window_times, spectral_complexity)
    
    def _calculate_gain_scaling(self, spectral_density: np.ndarray, spectral_complexity: np.ndarray) -> np.ndarray:
        """
        Calculate gain scaling factor based on signal characteristics.
        """
        # Base scaling factor of 1.0 (no change)
        gain_scale = np.ones_like(spectral_density)
        
        # Apply spectral density scaling
        if self.spectral_sensitivity > 0:
            # More spectral content = more noise
            gain_scale *= (1.0 + self.spectral_sensitivity * spectral_density)
        
        # Apply complexity scaling  
        if self.complexity_sensitivity > 0:
            # More spectral complexity = more noise
            gain_scale *= (1.0 + self.complexity_sensitivity * spectral_complexity)
        
        return gain_scale
    
    def _apply_spectral_matching(self, noise: np.ndarray, signal: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Apply spectral matching to make noise follow the frequency content of the signal.
        
        Args:
            noise: Base noise signal
            signal: Original audio signal to match
            sample_rate: Audio sample rate
            
        Returns:
            Spectrally-matched noise
        """
        if len(signal) == 0 or len(noise) == 0:
            return noise
        
        # Convert both to frequency domain
        signal_fft = np.fft.rfft(signal)
        noise_fft = np.fft.rfft(noise)
        
        # Get magnitude spectra
        signal_magnitude = np.abs(signal_fft)
        noise_magnitude = np.abs(noise_fft)
        
        # Smooth the signal spectrum to avoid extreme peaks
        if len(signal_magnitude) > 1:
            # Apply simple smoothing (moving average)
            kernel_size = max(1, len(signal_magnitude) // 32)  # Smooth over ~3% of spectrum
            if kernel_size > 1:
                kernel = np.ones(kernel_size) / kernel_size
                signal_magnitude_smooth = np.convolve(signal_magnitude, kernel, mode='same')
            else:
                signal_magnitude_smooth = signal_magnitude
        else:
            signal_magnitude_smooth = signal_magnitude
        
        # Create target spectrum by mixing signal spectrum with flat spectrum
        flat_spectrum = np.ones_like(signal_magnitude_smooth)
        target_spectrum = (1.0 - self.spectral_sensitivity) * flat_spectrum + \
                         self.spectral_sensitivity * signal_magnitude_smooth
        
        # Normalize target spectrum to prevent extreme amplification
        if np.max(target_spectrum) > 0:
            target_spectrum = target_spectrum / np.max(target_spectrum)
        
        # Apply spectral shaping to noise
        if len(noise_magnitude) > 0 and np.max(noise_magnitude) > 0:
            # Calculate shaping filter
            eps = 1e-10  # Prevent division by zero
            shaping_filter = target_spectrum / (noise_magnitude + eps)
            
            # Limit extreme values in shaping filter
            shaping_filter = np.clip(shaping_filter, 0.1, 10.0)
            
            # Apply shaping filter while preserving noise phase
            noise_phase = np.angle(noise_fft)
            shaped_magnitude = noise_magnitude * shaping_filter
            shaped_fft = shaped_magnitude * np.exp(1j * noise_phase)
            
            # Convert back to time domain
            shaped_noise = np.fft.irfft(shaped_fft, n=len(noise))
            
            # Normalize to prevent clipping
            if np.max(np.abs(shaped_noise)) > 0:
                shaped_noise = shaped_noise / np.max(np.abs(shaped_noise)) * np.max(np.abs(noise))
            
            return shaped_noise
        
        return noise