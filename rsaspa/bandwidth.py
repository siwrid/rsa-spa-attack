"""SPA key recovery by low-pass filtering and peak-height classification.

An independent front-end to the SAD method. Instead of template matching we:
  1. Low-pass filter the trace (Butterworth) to suppress noise and the carrier,
     leaving one clean peak per modular operation.
  2. Locate every operation peak with scipy.find_peaks.
  3. Classify each peak as a squaring or a multiply by its height (a 1-D
     two-means split): squarings draw more current than multiplies.
  4. Rebuild the exponent from the squaring / multiply sequence.

This recovers the full exponent -- including the last bit -- from peak heights
alone, and cross-checks the SAD result.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

from .rsa import ops_to_exponent
from .sad import two_means_threshold


def lowpass(x, cutoff_frac=0.02, order=4):
    """Zero-phase Butterworth low-pass. cutoff_frac is a fraction of Nyquist."""
    b, a = butter(order, cutoff_frac, btype="low")
    return filtfilt(b, a, np.asarray(x, dtype=float))


def recover_exponent(trace, expected_ops=None, *, op_len_hint=200,
                     cutoff_frac=0.02):
    """Recover the exponent from a trace using the filtered-peak method.

    expected_ops : optional total operation count, used to pick the filter
                   cutoff that yields that many peaks. If None, a default
                   cutoff is used.
    """
    trace = np.asarray(trace, dtype=float)
    env = lowpass(np.abs(trace), cutoff_frac)
    distance = int(0.6 * op_len_hint)

    cutoffs = [cutoff_frac] if expected_ops is None else \
        [0.008, 0.012, 0.016, 0.02, 0.025, 0.03, 0.04, 0.05]

    best = None
    for cf in cutoffs:
        e = lowpass(np.abs(trace), cf)
        prom = 0.08 * np.ptp(e)
        peaks, _ = find_peaks(e, distance=distance, prominence=prom)
        if expected_ops is None:
            best = (e, peaks, cf)
            break
        if len(peaks) == expected_ops:
            best = (e, peaks, cf)
            break
        if best is None:
            best = (e, peaks, cf)

    env, peaks, used_cutoff = best
    heights = env[peaks]
    thr = two_means_threshold(heights)
    labels = ["S" if h > thr else "M" for h in heights]

    exponent = ops_to_exponent(labels)
    return {
        "exponent": exponent,
        "labels": labels,
        "peaks": peaks,
        "heights": heights,
        "height_threshold": thr,
        "cutoff_frac": used_cutoff,
        "envelope": env,
    }
