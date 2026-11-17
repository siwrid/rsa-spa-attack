"""Simple Power Analysis (SPA) of RSA square-and-multiply.

A self-contained, hardware-free reconstruction of an SPA attack: instrument the
naive modular exponentiation, model its power leakage, then recover the secret
exponent from the trace by two independent methods (SAD template matching and
low-pass peak classification).
"""
from . import bandwidth, leakage, rsa, sad

__all__ = ["rsa", "leakage", "sad", "bandwidth"]
