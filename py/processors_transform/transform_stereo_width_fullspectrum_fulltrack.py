ALGO_VERSION = "v008"  # increment to signal algo or output schema changes and invalidate current cache
PROCESSOR_NAME = __name__.split('.')[-1]

import os
import numpy as np
import soundfile as sf
from scipy import signal

from zulu.fs_cache_utils import get_file_timestamp, get_keys

from zulu.InternalStorage import InternalStorage
from zulu.ConfigCompositeProfile import ConfigCompositeProfile

def process(profile: ConfigCompositeProfile, internal_storage: InternalStorage, session_data: dict, file_path: str, pipeline_options: dict = None, progress_callback = None) -> dict:
    """
    Experimental stereo width correction using frequency-selective Mid/Side processing.

    The correction is now time-dependent:
      - A time-domain envelope defines the peak correction per frame (linear or exponential).
      - A frequency-domain bell (Gaussian in log-freq) distributes that per frame across bins.
      - Edges (<= min_freq_hz or >= max_freq_hz) are always 0 correction.
    """

    configJSCSS = profile.load_config()
    if pipeline_options: configJSCSS.cascade_graph({PROCESSOR_NAME: pipeline_options})

    config = configJSCSS.query(path_filter = PROCESSOR_NAME, selector = None).to_graph()

    correction_fn = config.get("correction_fn", "linear")
    slope = float(config.get("slope", 0.5))
    x_1 = float(config.get("x_1", 0.5))
    flatness = float(config.get("flatness", 1))
    vertical_translation = float(config.get("vertical_translation", 0.0))     # linear: vertical offset; exponential: vertical_translation
    min_freq_hz = float(config.get("min_freq_hz", 1500))
    max_freq_hz = float(config.get("max_freq_hz", 2500))
    bell_curve_decay_speed = float(config.get("bell_curve_decay_speed", 1.0))
    window_samples = int(config.get("window_samples", 4096))
    hop_samples = int(config.get("hop_samples", 2048))
    window_type = config.get("window_type", "hann")

    (params, new_params_version) = get_keys({
        "_c_algo_ver": ALGO_VERSION,

        "_c_src_file_name": os.path.basename(file_path),
        "_c_src_file_timestamp": get_file_timestamp(file_path),

        "_c_correction_fn": correction_fn,
        "_c_slope": slope,
        "_c_x_1": x_1,
        "_c_flatness": flatness,
        "_c_vertical_translation": vertical_translation,
        "_c_min_freq_hz": min_freq_hz,
        "_c_max_freq_hz": max_freq_hz,
        "_c_bell_curve_decay_speed": bell_curve_decay_speed,
        "_c_window_samples": window_samples,
        "_c_hop_samples": hop_samples,
        "_c_window_type": window_type,
    })
    previous = internal_storage.get_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, {})
    if new_params_version == previous.get('params_version'):
        return {
            "from_cache": True,
            "data": previous,
        }
    if previous: internal_storage.remove(processor_name=PROCESSOR_NAME, params_version=previous.get('params_version'))

    src_path = internal_storage.add_file(PROCESSOR_NAME, ALGO_VERSION, new_params_version, os.path.basename(file_path), os.path.dirname(file_path))
    out_root = os.path.dirname(src_path)
    out_file_name = PROCESSOR_NAME + '.' + os.path.basename(src_path)
    out_path = os.path.join(out_root, out_file_name)

    # Validate frequency range
    if min_freq_hz <= 0 or max_freq_hz <= min_freq_hz:
        raise ValueError(f"Invalid frequency range: min_freq_hz ({min_freq_hz}) must be > 0 and max_freq_hz ({max_freq_hz}) must be > min_freq_hz")

    # Validate bell curve decay speed
    if bell_curve_decay_speed <= 0:
        raise ValueError(f"bell_curve_decay_speed ({bell_curve_decay_speed}) must be > 0")

    # Load stereo audio file
    subtype = sf.info(file_path).subtype
    data, sample_rate = sf.read(file_path)
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError("Audio file must be stereo")

    left_channel = data[:, 0]
    right_channel = data[:, 1]

    # Calculate STFT parameters
    noverlap = window_samples - hop_samples

    # Apply STFT to both channels
    freqs, times, stft_left = signal.stft(
        left_channel,
        fs=sample_rate,
        window=window_type,
        nperseg=window_samples,
        noverlap=noverlap
    )

    _, _, stft_right = signal.stft(
        right_channel,
        fs=sample_rate,
        window=window_type,
        nperseg=window_samples,
        noverlap=noverlap
    )

    # Convert to Mid/Side in frequency domain
    stft_mid = 0.5 * (stft_left + stft_right)
    stft_side = 0.5 * (stft_left - stft_right)

    # Build time vector t in [0,1] across frames (monotonic)
    if times.size == 0 or times[-1] == 0:
        t = np.zeros_like(times)
    else:
        t = times / times[-1]

    # Build per-frame envelope A_t according to selected curve
    if correction_fn == "linear":
        A_t = vertical_translation + slope * t
    elif correction_fn == "exponential":
        # A_t = (exp((t * flatness) / x_1) - 1) / (exp(flatness) - 1) + vertical_translation
        A_t = (np.exp((t * flatness) / x_1) - 1.0) / (np.exp(flatness) - 1.0) + vertical_translation
    else:
        raise ValueError('"linear" or "exponential"')

    # Frequency-only bell curve (Gaussian in log-frequency), edges forced to 0
    bell = gaussian_bell_logfreq(freqs, min_freq_hz, max_freq_hz, bell_curve_decay_speed)  # shape [F]

    # Combine time envelope with frequency bell: correction[f, t] = bell[f] * A_t[t]
    # Broadcast to [F, T]
    correction = bell[:, None] * A_t[None, :]

    # Apply to Side: stft_side_corrected = stft_side * (1 - correction), clamped to avoid negative scaling
    reduction = 1.0 - correction
    reduction = np.clip(reduction, 0.0, 1.0)
    stft_side_corrected = stft_side * reduction

    # Convert back to L/R
    stft_left_corrected = stft_mid + stft_side_corrected
    stft_right_corrected = stft_mid - stft_side_corrected

    # Reconstruct time domain signals
    _, left_corrected = signal.istft(
        stft_left_corrected,
        fs=sample_rate,
        window=window_type,
        nperseg=window_samples,
        noverlap=noverlap
    )

    _, right_corrected = signal.istft(
        stft_right_corrected,
        fs=sample_rate,
        window=window_type,
        nperseg=window_samples,
        noverlap=noverlap
    )

    # Combine channels
    output_data = np.column_stack((left_corrected, right_corrected))

    # Save corrected audio
    sf.write(out_path, output_data, sample_rate, subtype = subtype)

    data = {
        "params_version": new_params_version,
        "params": params,
        "result": {
            "dir_name": out_root,
            "file_name": out_file_name,
        }
    }

    internal_storage.set_data(PROCESSOR_NAME, ALGO_VERSION, new_params_version, data)

    return {
        "from_cache": False,
        "data": data
    }

def gaussian_bell_logfreq(freqs, min_freq_hz, max_freq_hz, bell_curve_decay_speed):
    """
    Frequency-only bell curve in log-frequency space.
    Peak = 1 at center, forced 0 at edges (<=min or >=max).
    """
    freqs = np.asarray(freqs, dtype=float)

    log_min = np.log(min_freq_hz)
    log_max = np.log(max_freq_hz)
    log_center =  (log_min + log_max) / 2.0
    log_std = (log_max - log_min) / 6.0 * bell_curve_decay_speed

    bell = np.zeros_like(freqs, dtype=float)

    # valid band (strictly inside)
    in_band = (freqs > min_freq_hz) & (freqs < max_freq_hz) & (freqs > 0.0)
    if not np.any(in_band) or log_std == 0.0:
        return bell

    log_f = np.zeros_like(freqs, dtype=float)
    log_f[in_band] = np.log(freqs[in_band])

    d = np.abs(log_f - log_center)
    bell[in_band] = np.exp(- (d[in_band] ** 2) / (2.0 * (log_std ** 2)))

    # edges remain 0 by construction via in_band
    return bell
