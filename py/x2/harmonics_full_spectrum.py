import os
import numpy as np
import soundfile as sf
from lib.chunk_parallel_process import chunk_parallel_process

def spectral_flatness(mag_spectrum):
    mag_spectrum = np.where(mag_spectrum == 0, 1e-12, mag_spectrum)
    geo_mean = np.exp(np.mean(np.log(mag_spectrum)))
    arith_mean = np.mean(mag_spectrum)
    return geo_mean / arith_mean if arith_mean != 0 else 0

def process_single_chunk(chunk_path, chunk, fft_size, step_size, band_limit_hz):
    try:
        data, rate = sf.read(chunk_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        spectrum_bins = int((fft_size // 2) * band_limit_hz / (rate / 2))

        flatness_values = []
        for i in range(0, len(data) - fft_size, step_size):
            frame = data[i:i+fft_size]
            windowed = frame * np.hanning(fft_size)
            mag = np.abs(np.fft.rfft(windowed))[:spectrum_bins]
            flatness_values.append(spectral_flatness(mag))

        avg_flatness = float(np.mean(flatness_values)) if flatness_values else None
        std_flatness = float(np.std(flatness_values)) if flatness_values else None
        
        return {
            "chunk": chunk,
            "overall_spectral_flatness_ratio": round(avg_flatness, 6) if avg_flatness is not None else None,
            "std_overall_spectral_flatness_ratio": round(std_flatness, 6) if std_flatness is not None else None
        }

    except Exception as e:
        return {
            "chunk": chunk,
            "overall_spectral_flatness_ratio": None,
            "std_overall_spectral_flatness_ratio": None,
            "error": str(e)
        }

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['fft_size'], ctx['step_size'], ctx['band_limit_hz'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    fft_size = int(config.get("harmonics_full_spectrum::fft_size", 4096))
    step_size = int(config.get("harmonics_full_spectrum::hop_size", 2048))
    band_limit_hz = int(config.get("harmonics_full_spectrum::band_limit_hz", 16000))
    max_workers = config.get("parallel::max_workers", None)

    # Create context object for callback
    context = {
        'fft_size': fft_size,
        'step_size': step_size,
        'band_limit_hz': band_limit_hz
    }

    # Process all chunks in parallel using processes
    results = chunk_parallel_process(_chunk_callback, chunk_list, out_path, context, max_workers, use_processes=False)

    return { "result": results }