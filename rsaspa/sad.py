"""SPA key recovery by Sum-of-Absolute-Differences (SAD) template matching.

Method (timing-based SPA):
  1. Take a reference slice of one squaring operation.
  2. Slide it over the trace and compute the SAD at every offset (sad_scan).
  3. Offsets where the SAD drops below a threshold are matches (hits); collapse
     clusters so each squaring contributes one timestamp.
  4. The gap to the next squaring is long when a multiply happened in between
     (exponent bit 1) and short when it did not (bit 0). A 1-D two-means split
     turns the gaps into bits.

The SAD threshold is auto-tuned to yield exactly the expected number of
squarings, which equals the exponent's bit length.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import find_peaks

from .rsa import ops_to_exponent


def sad_scan(trace, ref) -> np.ndarray:
    """Sum of absolute differences between ref and the trace at every offset."""
    trace = np.asarray(trace, dtype=float)
    ref = np.asarray(ref, dtype=float)
    windows = sliding_window_view(trace, len(ref))
    return np.sum(np.abs(windows - ref), axis=1)


def two_means_threshold(values, iters: int = 100) -> float:
    """1-D two-means (k=2) split; threshold is halfway between the cluster means."""
    values = np.asarray(values, dtype=float)
    if values.size < 2:
        raise ValueError("need at least two values to split")
    clipped = np.clip(values, np.percentile(values, 10), np.percentile(values, 85))
    thr = (clipped.min() + clipped.max()) / 2.0
    for _ in range(iters):
        low, high = clipped[clipped <= thr], clipped[clipped > thr]
        if low.size == 0 or high.size == 0:
            break
        updated = (low.mean() + high.mean()) / 2.0
        if abs(updated - thr) < 1e-12:
            break
        thr = updated
    return thr


def recover_exponent(trace, expected_bits=None, *, ref_start=None, ref_len=None,
                     op_len_hint=200):
    """Recover the exponent from a trace using the SAD template method.

    A squaring reference is matched against the whole trace. Every modular
    operation shows up as a local minimum of the SAD scan; a *squaring* matches
    the reference almost perfectly (SAD near zero) while a *multiply* matches
    only partially (larger SAD), because the two draw different current. A 1-D
    two-means split on the minima values labels each operation, and the
    square/multiply sequence is the exponent.

    expected_bits is optional and only used as a sanity check if provided.
    Returns a dict with the recovered integer and diagnostics.
    """
    trace = np.asarray(trace, dtype=float)
    ref_len = ref_len or op_len_hint
    ref_start = ref_start if ref_start is not None else _first_op_start(trace, op_len_hint)
    ref = trace[ref_start:ref_start + ref_len]

    diffs = sad_scan(trace, ref)

    # Each operation is a trough in the SAD scan. find_peaks on -diffs locates them.
    distance = int(0.6 * op_len_hint)
    prominence = 0.15 * np.ptp(diffs)
    troughs, _ = find_peaks(-diffs, distance=distance, prominence=prominence)
    if troughs.size == 0:
        raise RuntimeError("no operations detected in the SAD scan")

    values = diffs[troughs]
    match_thr = two_means_threshold(values)
    labels = ["S" if v < match_thr else "M" for v in values]

    # The first detected operation must be the leading squaring.
    if labels and labels[0] != "S":
        labels[0] = "S"

    exponent = ops_to_exponent(labels)
    squares = [int(t) for t, l in zip(troughs, labels) if l == "S"]

    return {
        "exponent": exponent,
        "labels": labels,
        "troughs": troughs,
        "values": values,
        "squares": squares,
        "sad_threshold": match_thr,
        "diffs": diffs,
        "ref": ref,
        "expected_bits": expected_bits,
    }


def _first_op_start(trace, op_len):
    """Find the start of the first operation, past the quiet settling region.

    Operations carry sustained energy; the settling region is only noise. A
    moving-average envelope separates the two robustly, unlike a raw-sample
    threshold that trips on isolated noise spikes.
    """
    env = np.convolve(np.abs(trace), np.ones(op_len) / op_len, mode="same")
    above = np.where(env > 0.3 * env.max())[0]
    return int(above[0]) if above.size else 0
