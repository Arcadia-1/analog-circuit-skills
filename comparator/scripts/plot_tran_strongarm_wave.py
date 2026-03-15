#!/usr/bin/env python3
"""plot_tran_strongarm_wave.py — 4-panel waveform figure."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

WAVE_PNG = PLOT_DIR / "strongarm_waveform.png"

C_CLK = "#555555"
C_INP = "#1a7abf";  C_INN = "#e84141"
C_VXP = "#1a7abf";  C_VXN = "#e84141"
C_VLP = "#2ca02c";  C_VLN = "#d62728"
C_OUTP = "#1a7abf"; C_OUTN = "#e84141"


def plot_wave(wave, params):
    """4-panel waveform: CLK/INP, VXP/VXN, VLP/VLN, OUTP/OUTN."""
    if wave is None or wave.get("time") is None:
        print("  WARN: no waveform data to plot")
        return

    t_ns = wave["time"] * 1e9
    VDD  = params["VDD"]

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(
        f"StrongArm Comparator — Transition Waveform\n"
        f"{params['L_NM']}nm PTM HP, VDD={VDD}V, CLK=1GHz, "
        f"Vin_diff={wave['vin_mv']:+.0f}mV",
        fontsize=12,
    )

    ax = axes[0]
    if wave["clk"] is not None:
        ax.plot(t_ns, wave["clk"], color=C_CLK, lw=1.5, label="CLK", zorder=3)
    if wave["inp"] is not None:
        ax2 = ax.twinx()
        ax2.plot(t_ns, (np.array(wave["inp"]) - params["VCM"]) * 1e3,
                 color=C_INP, lw=1.2, ls="--", label="INP-VCM")
        ax2.plot(t_ns, (np.array(wave["inn"]) - params["VCM"]) * 1e3,
                 color=C_INN, lw=1.2, ls="--", label="INN-VCM")
        ax2.set_ylabel("Input offset (mV)", fontsize=9)
        ax2.legend(loc="upper right", fontsize=8, ncol=2)
        ax2.set_ylim(-3, 3)
    ax.set_ylabel("CLK (V)", fontsize=9)
    ax.set_ylim(-0.1, VDD * 1.15)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_title("Clock & Differential Input", fontsize=9)

    ax = axes[1]
    if wave["vxp"] is not None:
        ax.plot(t_ns, wave["vxp"], color=C_VXP, lw=1.5, label="VXP (+)")
        ax.plot(t_ns, wave["vxn"], color=C_VXN, lw=1.5, label="VXN (-)")
    ax.axhline(VDD, color="gray", lw=0.7, ls=":")
    ax.axhline(0,   color="gray", lw=0.7, ls=":")
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.1)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.25)
    ax.set_title("Integration Nodes (VXP, VXN)", fontsize=9)

    ax = axes[2]
    if wave["vlp"] is not None:
        ax.plot(t_ns, wave["vlp"], color=C_VLP, lw=1.5, label="VLP (+)")
        ax.plot(t_ns, wave["vln"], color=C_VLN, lw=1.5, label="VLN (-)")
    ax.axhline(VDD / 2, color="gray", lw=0.7, ls=":", label=f"VDD/2={VDD/2}V")
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.1)
    ax.legend(fontsize=8, ncol=3)
    ax.grid(True, alpha=0.25)
    ax.set_title("Latch Nodes (VLP, VLN) — Positive Feedback", fontsize=9)

    ax = axes[3]
    if wave["outp"] is not None:
        ax.plot(t_ns, wave["outp"], color=C_OUTP, lw=1.8, label="OUTP (=1 when INP>INN)")
        ax.plot(t_ns, wave["outn"], color=C_OUTN, lw=1.8, label="OUTN (complement)")
    ax.axhline(VDD / 2, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_xlabel("Time (ns)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.1)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.25)
    ax.set_title("Output (OUTP, OUTN)", fontsize=9)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(WAVE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {WAVE_PNG.name}")
