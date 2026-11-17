"""Synthetic power-trace generator for a square-and-multiply exponentiation.

A real oscilloscope trace of the RSA routine is a train of current spikes, one
per modular operation. We model that: each operation becomes a characteristic
bump, concatenated in execution order, plus a settling region and Gaussian
measurement noise. Squares and multiplies are given slightly different
amplitudes, exactly the distinction a real square-and-multiply leaks.

No real captured data ships with this project -- every trace is generated here
from an operation sequence, so the attack is fully reproducible offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class LeakageModel:
    op_len: int = 200          # samples per modular operation
    square_amp: float = 1.00   # relative current draw of a squaring
    mult_amp: float = 0.62     # a multiply draws visibly less -> SPA distinguishes
    carrier_cycles: float = 6  # oscillation within one operation
    noise: float = 0.05        # Gaussian noise standard deviation
    settle: int = 400          # quiet samples before the first operation
    tail: int = 400            # quiet samples after the last operation
    seed: int | None = None
    _template: np.ndarray = field(default=None, repr=False)

    def _bump(self, amp: float) -> np.ndarray:
        t = np.linspace(0.0, 1.0, self.op_len, endpoint=False)
        envelope = np.hanning(self.op_len)
        carrier = 1.0 + 0.30 * np.sin(2 * np.pi * self.carrier_cycles * t)
        return amp * envelope * carrier


def simulate_trace(ops, model: LeakageModel | None = None):
    """Render an S/M operation sequence as a noisy power trace.

    Returns (trace, truth) where truth is a dict of ground-truth metadata
    (operation start indices and labels) used only to validate the attack.
    """
    model = model or LeakageModel()
    rng = np.random.default_rng(model.seed)

    bump_s = model._bump(model.square_amp)
    bump_m = model._bump(model.mult_amp)

    segments = [np.zeros(model.settle)]
    op_starts, op_labels = [], []
    cursor = model.settle
    for op in ops:
        op_starts.append(cursor)
        op_labels.append(op)
        bump = bump_s if op == "S" else bump_m
        segments.append(bump)
        cursor += len(bump)
    segments.append(np.zeros(model.tail))

    trace = np.concatenate(segments)
    trace = trace + rng.normal(0.0, model.noise, size=trace.shape)
    truth = {
        "op_starts": np.asarray(op_starts),
        "op_labels": op_labels,
        "square_starts": np.asarray([s for s, l in zip(op_starts, op_labels) if l == "S"]),
        "op_len": model.op_len,
    }
    return trace.astype(float), truth
