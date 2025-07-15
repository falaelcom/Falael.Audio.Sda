import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

def estimate_bit_depth(signal, tolerance=1e-6):
   """Estimate effective bit depth by analyzing quantization levels"""
   # Remove DC offset
   signal = signal - np.mean(signal)
   
   # Find unique amplitude levels (with tolerance for floating point precision)
   unique_levels = []
   sorted_signal = np.sort(np.abs(signal[signal != 0]))  # Remove zeros and sort
   
   if len(sorted_signal) == 0:
       return None, 0
   
   current_level = sorted_signal[0]
   unique_levels.append(current_level)
   
   for sample in sorted_signal[1:]:
       if abs(sample - current_level) > tolerance:
           unique_levels.append(sample)
           current_level = sample
   
   # Estimate bit depth from number of unique levels
   num_levels = len(unique_levels)
   if num_levels <= 1:
       return None, num_levels
   
   estimated_bits = np.log2(num_levels * 2)  # *2 because we only counted positive levels
   return estimated_bits, num_levels

def calculate_noise_floor(magnitude_spectrum, percentile=10):
   """Calculate noise floor from FFT spectrum"""
   # Use lower percentile of spectrum as noise floor estimate
   noise_floor = np.percentile(magnitude_spectrum, percentile)
   if noise_floor <= 0:
       return -120.0  # Very low floor
   return 20 * np.log10(noise_floor)

def detect_quantization_artifacts(signal, frame_size=1024):
   """Detect quantization artifacts using spectral analysis"""
   artifacts = []
   
   for i in range(0, len(signal) - frame_size, frame_size // 2):
       frame = signal[i:i+frame_size]
       
       # Remove DC
       frame = frame - np.mean(frame)
       
       if np.std(frame) == 0:
           continue
           
       # FFT analysis
       windowed = frame * np.hanning(frame_size)
       fft_mag = np.abs(np.fft.fft(windowed))
       
       # Look for quantization noise patterns
       # Quantization creates broadband noise floor
       noise_floor = calculate_noise_floor(fft_mag)
       
       # Calculate spectral slope (quantization noise is typically flat)
       freqs = np.arange(len(fft_mag))
       # Focus on mid-to-high frequencies where quantization noise is most apparent
       mid_idx = len(fft_mag) // 4
       high_idx = len(fft_mag) // 2
       
       if high_idx > mid_idx:
           mid_energy = np.mean(fft_mag[mid_idx:high_idx])
           high_energy = np.mean(fft_mag[high_idx:])
           
           if mid_energy > 0 and high_energy > 0:
               spectral_slope = 20 * np.log10(high_energy / mid_energy)
           else:
               spectral_slope = -60.0  # Default steep slope
       else:
           spectral_slope = -60.0
           
       artifacts.append({
           'noise_floor_db': noise_floor,
           'spectral_slope_db': spectral_slope
       })
   
   return artifacts

def analyze_band_quantization(band_signal, frame_size, bit_depth_tolerance, noise_percentile, chunk, range_key):
   """Analyze quantization for a single frequency band"""
   try:
       # Estimate bit depth
       est_bits, num_levels = estimate_bit_depth(band_signal, bit_depth_tolerance)
       
       # Detect quantization artifacts
       artifacts = detect_quantization_artifacts(band_signal, frame_size)
       
       if artifacts:
           avg_noise_floor = np.mean([a['noise_floor_db'] for a in artifacts])
           std_noise_floor = np.std([a['noise_floor_db'] for a in artifacts])
           avg_spectral_slope = np.mean([a['spectral_slope_db'] for a in artifacts])
           std_spectral_slope = np.std([a['spectral_slope_db'] for a in artifacts])
       else:
           avg_noise_floor = None
           std_noise_floor = None
           avg_spectral_slope = None
           std_spectral_slope = None
       
       # Calculate dynamic range (difference between peak and noise floor)
       peak_level = 20 * np.log10(np.max(np.abs(band_signal))) if np.max(np.abs(band_signal)) > 0 else -120.0
       if avg_noise_floor is not None:
           dynamic_range = peak_level - avg_noise_floor
       else:
           dynamic_range = None
       
       return {
           "chunk": chunk,
           "estimated_bits": round(est_bits, 2) if est_bits is not None else None,
           "unique_levels": num_levels,
           "avg_noise_floor_db": round(avg_noise_floor, 2) if avg_noise_floor is not None else None,
           "noise_floor_std_db": round(std_noise_floor, 2) if std_noise_floor is not None else None,
           "avg_spectral_slope_db": round(avg_spectral_slope, 2) if avg_spectral_slope is not None else None,
           "spectral_slope_std_db": round(std_spectral_slope, 2) if std_spectral_slope is not None else None,
           "dynamic_range_db": round(dynamic_range, 2) if dynamic_range is not None else None
       }

   except Exception as e:
       return {
           "chunk": chunk,
           "estimated_bits": None,
           "unique_levels": None,
           "avg_noise_floor_db": None,
           "noise_floor_std_db": None,
           "avg_spectral_slope_db": None,
           "spectral_slope_std_db": None,
           "dynamic_range_db": None,
           "error": str(e)
       }

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   chunk_list = previous.get("split", {}).get("chunks", [])
   if not chunk_list:
       return {"error": "Missing or empty split result."}

   # Get configuration
   frame_size = int(config.get("quantization::frame_size", 1024))
   bit_depth_tolerance = float(config.get("quantization::bit_depth_tolerance", 1e-6))
   noise_percentile = float(config.get("quantization::noise_percentile", 10))
   low_hz = int(config.get("multiband::cutoff_low_freqHz", 200))
   high_hz = int(config.get("multiband::cutoff_high_freqHz", 21000))
   bands = int(config.get("multiband::bands", 6))

   # Create logarithmic frequency bands
   log_start = np.log10(low_hz)
   log_end = np.log10(high_hz)
   log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

   # Initialize output grouped by frequency ranges
   output = {}
   for i in range(bands):
       f_low = log_edges[i]
       f_high = log_edges[i + 1]
       range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
       output[range_key] = []

   for chunk in chunk_list:
       chunk_path = os.path.join(out_path, chunk)
       try:
           data, rate = sf.read(chunk_path)
           if data.ndim > 1:
               data = np.mean(data, axis=1)  # Convert to mono
               
       except Exception as e:
           # Add error entries for all frequency ranges
           for i in range(bands):
               f_low = log_edges[i]
               f_high = log_edges[i + 1]
               range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
               output[range_key].append({
                   "chunk": chunk,
                   "estimated_bits": None,
                   "unique_levels": None,
                   "avg_noise_floor_db": None,
                   "noise_floor_std_db": None,
                   "avg_spectral_slope_db": None,
                   "spectral_slope_std_db": None,
                   "dynamic_range_db": None,
                   "error": str(e)
               })
           continue

       # Process each frequency band
       for i in range(bands):
           f_low = log_edges[i]
           f_high = log_edges[i + 1]
           range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"

           try:
               # Bandpass filter for this frequency range
               band_signal = bandpass(data, rate, f_low, f_high)
               
               # Analyze quantization for this band
               band_result = analyze_band_quantization(band_signal, frame_size, bit_depth_tolerance, noise_percentile, chunk, range_key)
               output[range_key].append(band_result)

           except Exception as e:
               output[range_key].append({
                   "chunk": chunk,
                   "estimated_bits": None,
                   "unique_levels": None,
                   "avg_noise_floor_db": None,
                   "noise_floor_std_db": None,
                   "avg_spectral_slope_db": None,
                   "spectral_slope_std_db": None,
                   "dynamic_range_db": None,
                   "error": str(e)
               })

   return {"result": output}
