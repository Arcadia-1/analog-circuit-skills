#!/usr/bin/env python3
"""plot_sweep_k_valid.py — Plot sigma_n vs k and P(1) vs k."""

import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import PLOT_DIR
from simulate_sweep_k_valid import VCM_FIXED, NCYC, NOISE_NT

OUT_PNG = PLOT_DIR / "sweep_k_valid.png"


def plot_k_valid(results, wall_s=None):
    k_mv     = np.array([r["k_mv"]     for r in results])
    sigma_uv = np.array([r["sigma_uv"] for r in results])
    p1       = np.array([r["p1"]       for r in results])

    valid = ~np.isnan(sigma_uv)
    sigma_med = np.nanmedian(sigma_uv)

    runtime_str = f"  |  runtime {wall_s:.1f}s" if wall_s is not None else ""
    title = (f"Single-Point Probit Validation: σ_n vs k\n"
             f"45nm PTM HP, VDD=1.0V, VCM={VCM_FIXED:.2f}V, CLK=1GHz  |  "
             f"{NCYC} cycles/point  |  NT={NOISE_NT*1e12:.0f}ps  "
             f"BW={1/(2*NOISE_NT)/1e9:.0f}GHz{runtime_str}")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(title, fontsize=10, fontweight="bold")

    # ── Left: sigma_n vs k ───────────────────────────────────────────────────
    ax0 = axes[0]
    ax0.plot(k_mv[valid], sigma_uv[valid], "o-", color="#1a7abf", lw=2, ms=7)
    ax0.axhline(sigma_med, color="gray", lw=1.0, ls="--",
                label=f"Median σ = {sigma_med:.0f} µV")
    ax0.fill_between(k_mv[valid],
                     sigma_med * 0.9, sigma_med * 1.1,
                     alpha=0.08, color="gray", label="±10% band")
    ax0.set_xlabel("k  (fixed differential input, mV)", fontsize=10)
    ax0.set_ylabel("σ_n  Extracted noise (µV)", fontsize=10)
    ax0.set_title("σ_n vs k  (should be flat if method is correct)", fontsize=10)
    ax0.legend(fontsize=9)
    ax0.grid(True, alpha=0.3)

    # ── Right: P(1) vs k ─────────────────────────────────────────────────────
    ax1 = axes[1]
    ax1.plot(k_mv, p1 * 100, "s-", color="#e65100", lw=2, ms=7)
    ax1.axhline(65, color="gray", lw=0.8, ls=":", label="65% / 95% sweet spot")
    ax1.axhline(95, color="gray", lw=0.8, ls=":")
    ax1.fill_between(k_mv, 65, 95, alpha=0.07, color="green",
                     label="Reliable P(1) range [65%, 95%]")
    ax1.set_xlabel("k  (fixed differential input, mV)", fontsize=10)
    ax1.set_ylabel("P(output = 1)  (%)", fontsize=10)
    ax1.set_title("P(1) vs k", fontsize=10)
    ax1.set_ylim(40, 105)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")
