#!/usr/bin/env python3
"""
plot_tran_bts_wave.py
=====================
Waveform figure for bootstrap switch: 3 panels.
  1. CLK + VIN
  2. VGATE + VIN (show bootstrap: VGATE tracks VIN + VDD)
  3. VSAMPLED vs VIN (show sampling fidelity)
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bootstrap_common import PLOT_DIR, VDD

OUT_PNG = PLOT_DIR / "bts_waveform.png"

C_CLK  = "#757575"
C_VIN  = "#1a7abf"
C_GATE = "#e65100"
C_SAMP = "#2e7d32"
C_BOOST = "#f57f17"


def plot_wave(results):
    """Generate 3-panel waveform figure."""
    wave = results
    t = wave["time"]
    if t is None:
        print("  WARNING: no waveform data to plot")
        return

    t_ns = t * 1e9
    params = wave["params"]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(
        f"Bootstrap Switch — Transient Waveform\n"
        f"180nm PTM, VDD={VDD}V, FCLK={params['FCLK']/1e6:.0f}MHz, "
        f"W_sw={params['W']['sw']}µm, CB={params['CB']*1e12:.0f}pF",
        fontsize=10, fontweight="bold",
    )

    # Panel 1: CLK + VIN
    ax1.plot(t_ns, wave["clk"], color=C_CLK, lw=1.0, label="CLK")
    ax1.plot(t_ns, wave["vin"], color=C_VIN, lw=1.5, label="VIN")
    ax1.set_ylabel("Voltage (V)")
    ax1.set_title("Clock and Input Signal", fontsize=9)
    ax1.legend(fontsize=8, loc="upper right")
    ax1.set_ylim(-0.2, VDD + 0.2)
    ax1.grid(True, alpha=0.3)

    # Panel 2: VGATE + VIN (bootstrap effect)
    ax2.plot(t_ns, wave["vin"], color=C_VIN, lw=1.2, ls="--", label="VIN")
    ax2.plot(t_ns, wave["vgate"], color=C_GATE, lw=1.5, label="VGATE")
    if wave["vboost"] is not None:
        # Shade the bootstrap voltage region
        sampling = wave["clk"] > VDD / 2
        vgate_samp = np.where(sampling, wave["vgate"], np.nan)
        ax2.plot(t_ns, vgate_samp, color=C_GATE, lw=2.0, alpha=0.8)

    ax2.axhline(VDD, color=C_CLK, lw=0.8, ls=":", alpha=0.5, label=f"VDD={VDD}V")
    ax2.set_ylabel("Voltage (V)")
    ax2.set_title("Gate Voltage — VGATE tracks VIN + VDD during sampling", fontsize=9)
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_ylim(-0.5, 2 * VDD + 0.5)
    ax2.grid(True, alpha=0.3)

    # Panel 3: VSAMPLED vs VIN
    ax3.plot(t_ns, wave["vin"], color=C_VIN, lw=1.2, ls="--", label="VIN")
    ax3.plot(t_ns, wave["vsampled"], color=C_SAMP, lw=1.5, label="VSAMPLED")
    ax3.set_ylabel("Voltage (V)")
    ax3.set_xlabel("Time (ns)")
    ax3.set_title("Sampled Output — tracks VIN during sampling, holds during reset", fontsize=9)
    ax3.legend(fontsize=8, loc="upper right")
    ax3.set_ylim(-0.2, VDD + 0.2)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")
