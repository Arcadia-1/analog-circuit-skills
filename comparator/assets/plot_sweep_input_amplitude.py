#!/usr/bin/env python3
"""
plot_sweep_input_amplitude.py
=============================
Single-panel plot: Tcmp (ps) vs Vin_diff (V, log x-axis).
Only resolved points are plotted.
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

OUT_PNG = PLOT_DIR / "sweep_input_amplitude.png"


def plot_input_amplitude(results):
    vin_v    = np.array([r["vin_v"]   for r in results])
    tcmp_ps  = np.array([r["tcmp_ps"] for r in results], dtype=float)
    resolved = np.array([r["resolved"] for r in results], dtype=bool)

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    fig.suptitle(
        "StrongArm — Decision Time vs Input Amplitude\n"
        f"45nm PTM HP, VDD={VDD}V, CLK=1GHz, 1 cycle per point, no noise",
        fontsize=12, fontweight="bold",
    )

    ax.semilogx(vin_v[resolved], tcmp_ps[resolved],
                "o-", color="#1a7abf", lw=2, ms=4)
    ax.set_xlabel("Vin_diff (V)", fontsize=10)
    ax.set_ylabel("Tcmp (ps)", fontsize=10)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_title("Tcmp vs Vin_diff  (only resolved points shown)", fontsize=10)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")
