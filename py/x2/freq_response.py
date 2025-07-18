import os
import numpy as np
import soundfile as sf
from lib.chunk_parallel_process import chunk_parallel_process

def process_single_chunk(chunk_path, chunk, fft_size, overlap, log_edges, bands, low_hz, high_hz, total_bandwidth):
    try:
        data, rate = sf.read(chunk_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # Convert to mono

        # Calculate step size for overlap
        step_size = int(fft_size * (1 - overlap))
        
        # Collect all FFT frames for this chunk
        frames_ffts = []
        for i in range(0, len(data) - fft_size, step_size):
            frame = data[i:i+fft_size]
            windowed = frame * np.hanning(fft_size)
            fft_mag = np.abs(np.fft.rfft(windowed))
            frames_ffts.append(fft_mag)
        
        if not frames_ffts:
            # Return error structure for all bands
            result = {}
            for i in range(bands):
                f_low = log_edges[i]
                f_high = log_edges[i + 1]
                range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
                result[range_key] = {
                    "chunk": chunk,
                    "avg_magnitude_db": None,
                    "error": "No frames processed"
                }
            return result

        # Average across all frames
        avg_fft = np.mean(frames_ffts, axis=0)
        
        # Convert to frequency bins
        freqs = np.fft.rfftfreq(fft_size, 1/rate)
        
        # Calculate total energy in the analysis range (low_hz to high_hz)
        analysis_mask = (freqs >= low_hz) & (freqs <= high_hz)
        total_energy = np.sum(avg_fft[analysis_mask])
        
        # Prevent division by zero
        if total_energy == 0:
            total_energy = 1e-12
        
        # Calculate expected energy density for uniform distribution
        expected_energy_density = total_energy / total_bandwidth
        
        # Calculate relative balance for each band
        result = {}
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i + 1]
            range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            
            # Find frequency bin indices for this band
            bin_mask = (freqs >= f_low) & (freqs <= f_high)
            
            if np.any(bin_mask):
                # Calculate band energy density (energy per Hz)
                band_energy = np.sum(avg_fft[bin_mask])
                band_width = f_high - f_low
                band_energy_density = band_energy / band_width
                
                # Calculate balance in dB (relative to uniform distribution)
                if band_energy_density > 0 and expected_energy_density > 0:
                    balance_db = 20 * np.log10(band_energy_density / expected_energy_density)
                else:
                    balance_db = -60.0  # Very low floor for empty bands
            else:
                balance_db = -60.0  # Very low floor for empty bands
            
            result[range_key] = {
                "chunk": chunk,
                "avg_magnitude_db": round(float(balance_db), 2)
            }
        
        return result

    except Exception as e:
        # Return error structure for all bands
        result = {}
        for i in range(bands):
            f_low = log_edges[i]
            f_high = log_edges[i + 1]
            range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
            result[range_key] = {
                "chunk": chunk,
                "avg_magnitude_db": None,
                "error": str(e)
            }
        return result

def _chunk_callback(chunk_index, chunk_filename, chunk_path, ctx):
    return process_single_chunk(chunk_path, chunk_filename, ctx['fft_size'], ctx['overlap'], 
                               ctx['log_edges'], ctx['bands'], ctx['low_hz'], ctx['high_hz'], ctx['total_bandwidth'])

def process(file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    chunk_list = previous.get("split", {}).get("chunks", [])
    if not chunk_list:
        return {"error": "Missing or empty split result."}

    fft_size = int(config.get("freq_response::fft_size", 4096))
    overlap = float(config.get("freq_response::overlap", 0.5))
    low_hz = int(config.get("multiband::cutoff_low_freqHz", 100))
    high_hz = int(config.get("multiband::cutoff_high_freqHz", 20000))
    bands = int(config.get("multiband::bands", 8))
    max_workers = config.get("parallel::max_workers", None)

    # Create logarithmic frequency bands
    log_start = np.log10(low_hz)
    log_end = np.log10(high_hz)
    log_edges = np.logspace(log_start, log_end, num=bands + 1, base=10)

    # Calculate total bandwidth for uniform distribution reference
    total_bandwidth = high_hz - low_hz

    # Create context object for callback
    context = {
        'fft_size': fft_size,
        'overlap': overlap,
        'log_edges': log_edges,
        'bands': bands,
        'low_hz': low_hz,
        'high_hz': high_hz,
        'total_bandwidth': total_bandwidth
    }

    # Process all chunks in parallel using processes
    chunk_results = chunk_parallel_process(_chunk_callback, chunk_list, out_path, context, max_workers, use_processes=False)

    # Initialize output grouped by frequency ranges
    output = {}
    for i in range(bands):
        f_low = log_edges[i]
        f_high = log_edges[i + 1]
        range_key = f"{int(f_low)}Hz-{int(f_high)}Hz"
        output[range_key] = []

    # Distribute results to output bands
    for chunk_result in chunk_results:
        for range_key in output.keys():
            if range_key in chunk_result:
                output[range_key].append(chunk_result[range_key])

    return {"result": output}