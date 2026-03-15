#!/usr/bin/env python3
"""
plot_sweep_vcm.py
=================
Single-panel plot: sigma_n (µV) vs VCM.
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
from comparator_common import VDD
from simulate_sweep_vcm import SWEEP_NCYC, SWEEP_TSTEP, SWEEP_NOISE_NT, VIN_FIXED_MV

OUT_PNG = PLOT_DIR / "sweep_vcm.png"


def plot_vcm(results, wall_s=None, n_cycles=None, out_png=None):
    vcm_v    = np.array([r["vcm"]      for r in results])
    sigma_uv = np.array([r["sigma_uv"] for r in results])
    n_pts    = len(results)

    ncyc        = n_cycles if n_cycles is not None else SWEEP_NCYC
    noise_bw_ghz = 1 / (2 * SWEEP_NOISE_NT) / 1e9
    cyc_str     = f"{ncyc} cycles/point"
    runtime_str = f"  |  runtime {wall_s:.1f}s" if wall_s is not None else ""
    subtitle1   = (f"45nm PTM HP, VDD={VDD}V, CLK=1GHz  |  "
                   f"{n_pts} VCM points, {cyc_str}{runtime_str}")
    subtitle2   = (f"tstep={SWEEP_TSTEP*1e12:.0f}ps  |  "
                   f"NT={SWEEP_NOISE_NT*1e12:.0f}ps  |  "
                   f"noise BW={noise_bw_ghz:.1f}GHz  |  "
                   f"Vin_fixed={VIN_FIXED_MV}mV (probit method)")

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle(
        "StrongArm — Input-Referred Noise σ_n vs Common-Mode Voltage\n"
        + subtitle1 + "\n" + subtitle2,
        fontsize=10, fontweight="bold",
    )

    ax.plot(vcm_v, sigma_uv, "o-", color="#1a7abf", lw=2, ms=7)
    ax.axvline(VDD / 2, color="gray", lw=0.8, ls="--", label=f"VDD/2 = {VDD/2:.2f}V")
    ax.set_ylabel("σ_n  Input-referred noise (µV)", fontsize=10)
    ax.set_xlabel("VCM (V)", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_title("Input-Referred Noise σ_n vs VCM", fontsize=10)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = Path(out_png) if out_png is not None else OUT_PNG
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {save_path}")
