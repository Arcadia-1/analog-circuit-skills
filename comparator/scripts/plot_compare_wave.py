#!/usr/bin/env python3
"""
plot_compare_wave.py
====================
Two PNG files comparing StrongArm vs Miyahara waveforms.

PNG 1 — compare_waveform_se.png   (single-ended)
  Row 1: CLK + INP/INN
  Row 2: VLP & VLN for both topologies (4 lines)
  Row 3: OUTP & OUTN for both topologies (4 lines)

PNG 2 — compare_waveform_diff.png  (differential)
  Row 1: CLK + INP/INN
  Row 2: (VLP − VLN) for SA vs Miyahara
  Row 3: (OUTP − OUTN) for SA vs Miyahara

Polarity note:
  StrongArm : OUTP = NOT(VLP) → VLP→0 when INP > INN
  Miyahara  : OUTP = NOT(VLN) → VLN→0 when INP > INN
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

SE_PNG   = lambda label: PLOT_DIR / f"compare_waveform_se_{label}.png"
DIFF_PNG = lambda label: PLOT_DIR / f"compare_waveform_diff_{label}.png"

C_CLK     = "#555555"
C_INP     = "#2ca02c";  C_INN = "#d62728"
C_SA_VLP  = "#1a7abf";  C_SA_VLN  = "#8fb8d8"
C_MIY_VLP = "#e07b00";  C_MIY_VLN = "#f5b87a"
C_SA_OUT  = "#1a7abf";  C_SA_OUTN = "#8fb8d8"
C_MIY_OUT = "#e07b00";  C_MIY_OUTN = "#f5b87a"
C_SA_DIFF  = "#1a7abf"
C_MIY_DIFF = "#e07b00"


def _row1_clk_input(ax, t_sa, sa, vin_mv):
    ax.plot(t_sa, sa["clk"], color=C_CLK, lw=1.8, label="CLK", zorder=3)
    ax2 = ax.twinx()
    ax2.plot(t_sa, (np.array(sa["inp"]) - VCM) * 1e3,
             color=C_INP, lw=1.2, ls="--", label=f"INP−VCM (+{vin_mv/2:.2f}mV)")
    ax2.plot(t_sa, (np.array(sa["inn"]) - VCM) * 1e3,
             color=C_INN, lw=1.2, ls="--", label=f"INN−VCM (−{vin_mv/2:.2f}mV)")
    ax2.set_ylabel("Input (mV)", fontsize=9)
    ax2.set_ylim(-3, 3)
    ax2.legend(loc="upper right", fontsize=8, ncol=2)
    ax.set_ylabel("CLK (V)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.15)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_title("CLK & Differential Input  (identical for both topologies)", fontsize=9)


def _vin_label(vin_mv):
    """Compact filename label: 1.0mV → '1mV', 0.001mV (=1µV) → '1uV'."""
    if abs(vin_mv) >= 1.0:
        return f"{vin_mv:g}mV"
    uv = vin_mv * 1000
    return f"{uv:g}uV"


def plot_compare_se(sa, miy, vin_mv=1.0):
    """PNG 1: single-ended VLP/VLN and OUTP/OUTN."""
    if sa.get("time") is None or miy.get("time") is None:
        print("  WARN: missing data for SE plot")
        return

    label = _vin_label(vin_mv)
    t_sa  = sa["time"]  * 1e9
    t_miy = miy["time"] * 1e9
    out   = SE_PNG(label)

    # title: show vin in natural units
    vin_str = f"+{vin_mv:.3g}mV" if vin_mv >= 0.001 else f"+{vin_mv*1e3:.3g}µV"

    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(
        f"StrongArm vs Miyahara — Single-Ended Waveforms\n"
        f"45nm PTM HP, VDD={VDD}V, CLK=1GHz, Vin_diff={vin_str}, 3 cycles",
        fontsize=12, fontweight="bold",
    )

    _row1_clk_input(axes[0], t_sa, sa, vin_mv)

    ax = axes[1]
    ax.plot(t_sa,  sa["vlp"],  color=C_SA_VLP,  lw=2.0, label="VLP [SA]")
    ax.plot(t_sa,  sa["vln"],  color=C_SA_VLN,  lw=2.0, label="VLN [SA]")
    ax.plot(t_miy, miy["vlp"], color=C_MIY_VLP, lw=1.6, ls="--", label="VLP [Miyahara]")
    ax.plot(t_miy, miy["vln"], color=C_MIY_VLN, lw=1.6, ls="--", label="VLN [Miyahara]")
    ax.axhline(VDD / 2, color="gray", lw=0.7, ls=":", label="VDD/2")
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.1)
    ax.legend(fontsize=8, ncol=5)
    ax.grid(True, alpha=0.25)
    ax.set_title("Latch Nodes VLP & VLN  (SA=blue, Miyahara=orange)", fontsize=9)

    ax = axes[2]
    ax.plot(t_sa,  sa["outp"],  color=C_SA_OUT,   lw=2.0, label="OUTP [SA]")
    ax.plot(t_sa,  sa["outn"],  color=C_SA_OUTN,  lw=2.0, ls=":", label="OUTN [SA]")
    ax.plot(t_miy, miy["outp"], color=C_MIY_OUT,  lw=1.6, ls="--", label="OUTP [Miyahara]")
    ax.plot(t_miy, miy["outn"], color=C_MIY_OUTN, lw=1.6, ls="-.", label="OUTN [Miyahara]")
    ax.axhline(VDD / 2, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_xlabel("Time (ns)", fontsize=9)
    ax.set_ylim(-0.05, VDD * 1.1)
    ax.legend(fontsize=8, ncol=4)
    ax.grid(True, alpha=0.25)
    ax.set_title("Output OUTP & OUTN  (SA=blue, Miyahara=orange)", fontsize=9)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out}")


def plot_compare_diff(sa, miy, vin_mv=1.0):
    """PNG 2: differential (VLP−VLN) and (OUTP−OUTN)."""
    if sa.get("time") is None or miy.get("time") is None:
        print("  WARN: missing data for diff plot")
        return

    label   = _vin_label(vin_mv)
    t_sa    = sa["time"]  * 1e9
    t_miy   = miy["time"] * 1e9
    out     = DIFF_PNG(label)
    vin_str = f"+{vin_mv:.3g}mV" if vin_mv >= 0.001 else f"+{vin_mv*1e3:.3g}µV"

    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(
        f"StrongArm vs Miyahara — Differential Waveforms\n"
        f"45nm PTM HP, VDD={VDD}V, CLK=1GHz, Vin_diff={vin_str}, 3 cycles",
        fontsize=12, fontweight="bold",
    )

    _row1_clk_input(axes[0], t_sa, sa, vin_mv)

    ax = axes[1]
    ax.plot(t_sa,  np.array(sa["vlp"])  - np.array(sa["vln"]),
            color=C_SA_DIFF,  lw=2.0, label="VLP−VLN [SA]")
    ax.plot(t_miy, np.array(miy["vlp"]) - np.array(miy["vln"]),
            color=C_MIY_DIFF, lw=1.6, ls="--", label="VLP−VLN [Miyahara]")
    ax.axhline(0, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("VLP − VLN (V)", fontsize=9)
    ax.set_ylim(-VDD * 1.1, VDD * 1.1)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.25)
    ax.set_title("Differential Latch Voltage (VLP − VLN)", fontsize=9)

    ax = axes[2]
    ax.plot(t_sa,  np.array(sa["outp"])  - np.array(sa["outn"]),
            color=C_SA_DIFF,  lw=2.0, label="OUTP−OUTN [SA]")
    ax.plot(t_miy, np.array(miy["outp"]) - np.array(miy["outn"]),
            color=C_MIY_DIFF, lw=1.6, ls="--", label="OUTP−OUTN [Miyahara]")
    ax.axhline(0, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("OUTP − OUTN (V)", fontsize=9)
    ax.set_xlabel("Time (ns)", fontsize=9)
    ax.set_ylim(-VDD * 1.1, VDD * 1.1)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.25)
    ax.set_title("Differential Output Voltage (OUTP − OUTN)", fontsize=9)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out}")


def plot_compare(sa, miy, vin_mv=1.0):
    """Produce both PNGs."""
    plot_compare_se(sa, miy, vin_mv)
    plot_compare_diff(sa, miy, vin_mv)
