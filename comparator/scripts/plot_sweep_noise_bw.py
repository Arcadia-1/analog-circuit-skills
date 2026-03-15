#!/usr/bin/env python3
"""
plot_sweep_noise_bw.py
======================
PNG: sigma_n (µV) vs noise bandwidth (GHz).
"""

import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import PLOT_DIR
from comparator_common import VDD, VCM
from simulate_sweep_noise_bw import BW_START, BW_STOP, N_BW, VIN_MV_VALS, SWEEP_TSTEP

OUT_PNG = PLOT_DIR / "sweep_noise_bw.png"


def plot_noise_bw(results, wall_s=None):
    if not results:
        print("  WARN: no results to plot")
        return

    bw_ghz   = np.array([r["bw_ghz"]   for r in results])
    sigma_uv = np.array([r["sigma_uv"] for r in results])
    nt_ps    = np.array([r["nt_ps"]    for r in results])

    runtime_str = f"  |  runtime {wall_s:.1f}s" if wall_s is not None else ""
    subtitle1 = (f"45nm PTM HP, VDD={VDD}V, CLK=1GHz, VCM={VCM}V  |  "
                 f"{N_BW} BW points, {len(VIN_MV_VALS)} Vin per point{runtime_str}")
    subtitle2 = (f"tstep={SWEEP_TSTEP*1e12:.0f}ps  |  "
                 f"NT=1/(2·BW)  |  adaptive cycles  |  reltol=0.001 (default)")

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.suptitle(
        "StrongArm — Input-Referred Noise σ_n vs Noise Source Bandwidth\n"
        + subtitle1 + "\n" + subtitle2,
        fontsize=10, fontweight="bold",
    )

    ax.semilogx(bw_ghz, sigma_uv, "o-", color="#1a7abf", lw=2, ms=8)

    # annotate each point with its NT
    for bw, sig, nt in zip(bw_ghz, sigma_uv, nt_ps):
        ax.annotate(f"NT={nt:.0f}ps", (bw, sig),
                    textcoords="offset points", xytext=(4, 6),
                    fontsize=7, color="#444")

    ax.set_xlabel("Noise Bandwidth (GHz)  [log scale]", fontsize=10)
    ax.set_ylabel("σ_n  Input-referred noise (µV)", fontsize=10)
    ax.set_title("σ_n vs Noise Bandwidth  (BW = 1/(2·NT))", fontsize=10)
    ax.grid(True, which="both", alpha=0.3)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")
