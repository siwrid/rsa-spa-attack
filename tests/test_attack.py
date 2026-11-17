"""Self-tests: the two SPA methods recover known exponents, and RSA is consistent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from rsaspa import bandwidth, sad  # noqa: E402
from rsaspa.leakage import LeakageModel, simulate_trace  # noqa: E402
from rsaspa.rsa import (generate_key, modexp_square_multiply,  # noqa: E402
                        ops_to_exponent)


def _trace_for(exp, seed=0, noise=0.05):
    _, ops = modexp_square_multiply(3, exp, (1 << (exp.bit_length() + 8)) | 1)
    trace, _ = simulate_trace(ops, LeakageModel(noise=noise, seed=seed))
    return trace, ops


def test_modexp_matches_builtin():
    base, exp, mod = 7, 0x8AB0, 1000003
    result, ops = modexp_square_multiply(base, exp, mod)
    assert result == pow(base, exp, mod)
    assert ops_to_exponent(ops) == exp
    assert ops.count("S") == exp.bit_length()
    print("ok   modexp result + op-sequence round-trip")


def test_rsa_sign_verify():
    key = generate_key(128)
    msg = 123456789 % key.n
    sig, _ = key.sign(msg)
    assert key.verify(msg, sig)
    assert not key.verify(msg + 1, sig)
    print("ok   generated RSA key signs and verifies")


def test_sad_recovers_lab_key():
    exp = 0x8AB0
    trace, _ = _trace_for(exp, seed=3)
    r = sad.recover_exponent(trace, exp.bit_length())
    assert r["exponent"] == exp, f"SAD got 0x{r['exponent']:X}"
    print("ok   SAD recovers 0x8AB0")


def test_bandwidth_recovers_lab_key():
    exp = 0x8AB0
    trace, ops = _trace_for(exp, seed=3)
    r = bandwidth.recover_exponent(trace, expected_ops=len(ops))
    assert r["exponent"] == exp, f"BW got 0x{r['exponent']:X}"
    print("ok   low-pass peak method recovers 0x8AB0")


def test_both_methods_random_keys():
    for seed in range(6):
        key = generate_key(48)
        exp = key.d
        trace, ops = _trace_for(exp, seed=seed, noise=0.07)
        r_sad = sad.recover_exponent(trace, exp.bit_length())
        r_bw = bandwidth.recover_exponent(trace, expected_ops=len(ops))
        assert r_sad["exponent"] == exp, f"SAD seed {seed}"
        assert r_bw["exponent"] == exp, f"BW seed {seed}"
    print("ok   both methods recover 6 random exponents")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print("\nall passed" if not failed else f"\n{failed} test(s) failed")
    sys.exit(1 if failed else 0)
