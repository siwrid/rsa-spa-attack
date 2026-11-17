"""Textbook RSA with an instrumented square-and-multiply exponentiation.

The point of interest for side-channel analysis is `modexp_square_multiply`,
which returns not just the result but the exact sequence of modular operations
it performed. A left-to-right binary exponentiation squares once per exponent
bit and multiplies only when the bit is 1 -- so the operation sequence reveals
the exponent. A power trace of this routine leaks the same sequence, which is
what the attack in this package recovers.

This is deliberately the naive, unprotected algorithm. Real libraries use
constant-time / blinded exponentiation precisely to stop this.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass


def modexp_square_multiply(base: int, exp: int, mod: int):
    """Compute base**exp % mod, recording each operation.

    Returns (result, ops) where ops is a list of "S" (square) and "M" (multiply)
    in execution order. The first operation is always a square of the leading 1.
    """
    if exp == 0:
        return 1 % mod, []
    result = 1
    ops: list[str] = []
    for bit in bin(exp)[2:]:  # most-significant bit first; leading bit is 1
        result = (result * result) % mod
        ops.append("S")
        if bit == "1":
            result = (result * base) % mod
            ops.append("M")
    return result, ops


def ops_to_exponent(ops: list[str]) -> int:
    """Inverse of the leak: rebuild the exponent from an S/M operation sequence."""
    bits = []
    i = 0
    n = len(ops)
    while i < n:
        if ops[i] != "S":
            raise ValueError(f"expected a square at position {i}, got {ops[i]!r}")
        if i + 1 < n and ops[i + 1] == "M":
            bits.append("1")
            i += 2
        else:
            bits.append("0")
            i += 1
    return int("".join(bits), 2) if bits else 0


# --- a small but genuine RSA key, so sign/verify actually works ---------

def _is_probable_prime(n: int, rounds: int = 40) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = 2 + secrets.randbelow(n - 3)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


@dataclass
class RsaKey:
    n: int
    e: int
    d: int
    bits: int

    def sign(self, message: int):
        """Raw RSA signature message**d mod n, returning (signature, ops)."""
        return modexp_square_multiply(message % self.n, self.d, self.n)

    def verify(self, message: int, signature: int) -> bool:
        return pow(signature, self.e, self.n) == message % self.n


def generate_key(bits: int = 256, e: int = 65537) -> RsaKey:
    """Generate a real RSA key of the given modulus size (small, for demos)."""
    half = bits // 2
    while True:
        p, q = _random_prime(half), _random_prime(half)
        if p == q:
            continue
        n = p * q
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        d = pow(e, -1, phi)
        return RsaKey(n=n, e=e, d=d, bits=n.bit_length())
