"""End-to-end SPA demo: leak a secret exponent from a simulated power trace.

    python -m demo.attack_demo [--bits N] [--key HEX] [--plot] [--seed S]

Generates (or accepts) a secret exponent, renders a synthetic power trace of the
square-and-multiply exponentiation, and recovers the exponent by both the SAD
and the low-pass-peak methods -- then checks the recovered value is correct.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rsaspa import bandwidth, sad  # noqa: E402
from rsaspa.leakage import LeakageModel, simulate_trace  # noqa: E402
from rsaspa.rsa import generate_key, modexp_square_multiply  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key", help="secret exponent in hex (e.g. 0x8AB0); overrides --bits")
    ap.add_argument("--bits", type=int, default=64, help="RSA modulus size for a generated key")
    ap.add_argument("--seed", type=int, default=1, help="trace noise seed (reproducible)")
    ap.add_argument("--noise", type=float, default=0.05, help="measurement noise stddev")
    ap.add_argument("--plot", action="store_true", help="save trace/analysis figures")
    args = ap.parse_args(argv)

    # 1. Choose the secret exponent.
    if args.key:
        secret = int(args.key, 16)
        base, mod = 3, (1 << (secret.bit_length() + 8)) | 1
        print(f"Secret exponent (given): 0x{secret:X}  ({secret.bit_length()} bits)")
    else:
        key = generate_key(args.bits)
        secret = key.d
        base, mod = 42 % key.n, key.n
        print(f"Generated RSA-{key.bits} key; attacking the private exponent d")
        print(f"Secret exponent d: 0x{secret:X}  ({secret.bit_length()} bits)")

    # 2. Run the exponentiation and render its power trace.
    _, ops = modexp_square_multiply(base, secret, mod)
    model = LeakageModel(noise=args.noise, seed=args.seed)
    trace, truth = simulate_trace(ops, model)
    print(f"\nExecuted {ops.count('S')} squares + {ops.count('M')} multiplies "
          f"= {len(ops)} operations")
    print(f"Simulated trace: {len(trace)} samples "
          f"(noise sigma={args.noise}, seed={args.seed})")

    expected_bits = secret.bit_length()

    # 3a. SAD template-matching attack.
    r_sad = sad.recover_exponent(trace, expected_bits, op_len_hint=model.op_len)
    ok_sad = r_sad["exponent"] == secret
    print("\n[SAD] template matching on squaring timing")
    print(f"  found {len(r_sad['squares'])} squarings, SAD thr={r_sad['sad_threshold']:.1f}")
    print(f"  recovered: 0x{r_sad['exponent']:X}  -> {'CORRECT' if ok_sad else 'WRONG'}")

    # 3b. Low-pass peak-height attack.
    r_bw = bandwidth.recover_exponent(trace, expected_ops=len(ops), op_len_hint=model.op_len)
    ok_bw = r_bw["exponent"] == secret
    print("\n[BW]  low-pass filter + peak-height classification")
    print(f"  found {len(r_bw['peaks'])} operation peaks, cutoff={r_bw['cutoff_frac']}")
    print(f"  recovered: 0x{r_bw['exponent']:X}  -> {'CORRECT' if ok_bw else 'WRONG'}")

    if args.plot:
        _plot(trace, truth, r_sad, r_bw, secret)

    print("\nResult:",
          "both methods recovered the secret exponent."
          if ok_sad and ok_bw else "at least one method failed.")
    return 0 if (ok_sad and ok_bw) else 1


def _plot(trace, truth, r_sad, r_bw, secret):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = Path(__file__).resolve().parent.parent / "figures"
    outdir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(3, 1, figsize=(11, 7), constrained_layout=True)
    ax[0].plot(trace, lw=0.5, color="crimson")
    ax[0].set(title="Simulated RSA power trace (square-and-multiply)", ylabel="power")
    ax[1].plot(r_sad["diffs"], lw=0.7, color="navy")
    ax[1].axhline(r_sad["sad_threshold"], ls="--", color="k",
                  label=f"SAD thr={r_sad['sad_threshold']:.1f}")
    for s in r_sad["squares"]:
        ax[1].axvline(s, color="green", alpha=0.25)
    ax[1].set(title="SAD scan: each dip is one squaring", ylabel="SAD")
    ax[1].legend(loc="upper right")
    ax[2].plot(r_bw["envelope"], lw=0.7, color="darkorange")
    ax[2].plot(r_bw["peaks"], r_bw["heights"], "k.", ms=4)
    ax[2].axhline(r_bw["height_threshold"], ls="--", color="k",
                  label="square/multiply split")
    ax[2].set(title="Low-pass envelope: tall peaks are squarings, short are multiplies",
              ylabel="envelope", xlabel="sample")
    ax[2].legend(loc="upper right")
    path = outdir / f"spa_0x{secret:X}.png"
    fig.savefig(path, dpi=110)
    print(f"\nFigure saved to {path}")


if __name__ == "__main__":
    raise SystemExit(main())
