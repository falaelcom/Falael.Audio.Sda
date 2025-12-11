import scipy.signal
import numpy as np

def bandpass(data, rate, low, high, use_fft=True):
    """
    Apply bandpass filter using either SOS Butterworth or FFT-based filtering
    
    Args:
        data: Input signal array
        rate: Sample rate
        low: Low frequency cutoff (Hz)
        high: High frequency cutoff (Hz)
        use_fft: If True, use FFT-based filtering with perfect reconstruction.
                 If False, use Butterworth filter (creates artifacts)
    
    Returns:
        Filtered signal array
    """
    if use_fft:
        return _fft_bandpass(data, rate, low, high)
    else:
        return _butterworth_bandpass(data, rate, low, high)

def _butterworth_bandpass(data, rate, low, high):
    """
    Original Butterworth bandpass filter (creates artifacts for testing degradation)
    """
    nyq = 0.5 * rate
    if high / nyq >= 1.0 or low / nyq <= 0:
        raise ValueError("Digital filter critical frequencies must be 0 < Wn < 1")
    
    # Use SOS format for better numerical stability
    sos = scipy.signal.butter(4, [low / nyq, high / nyq], btype='band', output='sos')
    return scipy.signal.sosfilt(sos, data)

def _fft_bandpass(data, rate, low, high):
    """
    FFT-based bandpass filter with perfect reconstruction properties.
    """
    if len(data) == 0:
        return data
    
    # Convert to frequency domain
    fft_data = np.fft.rfft(data)
    freqs = np.fft.rfftfreq(len(data), 1/rate)
    
    # Create sharp frequency mask with inclusive bounds
    # Use >= for low bound and < for high bound to avoid overlaps
    mask = (freqs >= low) & (freqs < high)
    
    # Special case: for the highest band, include the high frequency
    nyquist = rate / 2
    if high >= nyquist * 0.99:  # If this is effectively the top band
        mask = (freqs >= low)  # Include everything above low_hz
    
    # Apply mask and convert back to time domain
    fft_filtered = fft_data * mask
    return np.fft.irfft(fft_filtered, n=len(data))