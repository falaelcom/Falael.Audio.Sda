import os
import numpy as np
import soundfile as sf

from .lib.bandpass_filter import bandpass

def spectral_flatness(mag_spectrum):
   mag_spectrum = np.where(mag_spectrum == 0, 1e-12, mag_spectrum)
   geo_mean = np.exp(np.mean(np.log(mag_spectrum)))
   arith_mean = np.mean(mag_spectrum)
   return geo_mean / arith_mean if arith_mean != 0 else 0

def analyze_band_harmonics(band_signal, fft_size, step_size, chunk, range_key):
    """Analyze harmonics for a single frequency band"""
    try:
        flatness_values = []
        
        for i in range(0, len(band_signal) - fft_size, step_size):
            frame = band_signal[i:i+fft_size]
            windowed = frame * np.hanning(fft_size)
            mag = np.abs(np.fft.rfft(windowed))
            flatness_values.append(spectral_flatness(mag))

        avg_flatness = float(np.mean(flatness_values)) if flatness_values else None
        
        # Use only the logarithmic dB scale for maximum contrast
        if avg_flatness is not None and avg_flatness > 0:
            # Convert to dB-like scale: -log10(flatness) * 10
            # Lower flatness = higher dB value (more tonal)
            richness_db = -np.log10(avg_flatness) * 10
            richness_db = round(richness_db, 2)
        else:
            richness_db = None
        
        return {
            "chunk": chunk,
            "richness_db": richness_db
        }

    except Exception as e:
        return {
            "chunk": chunk,
            "richness_db": None,
            "error": str(e)
        }

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
   chunk_list = previous.get("split", {}).get("chunks", [])
   if not chunk_list:
       return {"error": "Missing or empty split result."}

   # Get configuration
   fft_size = int(config.get("harmonics::fft_size", 4096))
   step_size = int(config.get("harmonics::hop_size", 2048))
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
                   "richness_db": None,
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
               
               # Analyze harmonics for this band
               band_result = analyze_band_harmonics(band_signal, fft_size, step_size, chunk, range_key)
               output[range_key].append(band_result)

           except Exception as e:
               output[range_key].append({
                   "chunk": chunk,
                   "richness_db": None,
                   "error": str(e)
               })

   return {"result": output}