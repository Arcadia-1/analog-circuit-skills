#!/usr/bin/env python3
"""Plot helpers for two-stage op amp simulations."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR


def plot_ac(result):
    ac = result["ac"]
    freq = ac["freq"]
    gain = ac["gain_db"]
    phase = ac["phase"]
    if freq is None or gain is None:
        return

    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(7.2, 6.2), sharex=True)
    ax0.semilogx(freq, gain, lw=2)
    ax0.axhline(0, color="0.45", ls="--", lw=1)
    ax0.set_ylabel("Gain (dB)")
    ax0.grid(True, which="both", alpha=0.3)

    if phase is not None:
        ax1.semilogx(freq, phase, color="#d35400", lw=2)
    ax1.axhline(-180, color="0.45", ls="--", lw=1)
    ax1.set_xlabel("Frequency (Hz)")
    ax1.set_ylabel("Phase (deg)")
    ax1.grid(True, which="both", alpha=0.3)

    m = result.get("metrics", {})
    fig.suptitle(
        f"Two-Stage Op Amp AC Sweep  "
        f"Av0={m.get('dc_gain_db', float('nan')):.1f} dB, "
        f"UGB={m.get('ugb_hz', float('nan'))/1e6:.1f} MHz, "
        f"PM={m.get('phase_margin_deg', float('nan')):.1f} deg"
    )
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / "opamp_ac.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> opamp_ac.png")


def plot_noise(result):
    n = result["noise"]
    freq = n["freq"]
    onoise = n["onoise"]
    if freq is None or onoise is None:
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.loglog(freq, np.abs(onoise) * 1e9, lw=2)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Output noise (nV/rtHz)")
    ax.set_title("Two-Stage Op Amp Output Noise")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / "opamp_noise.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> opamp_noise.png")


def plot_dc_nodes(result):
    nodes = result["dc"]["nodes"]
    if not nodes:
        return

    names = ["pbias", "c", "a", "b", "out"]
    values = [nodes.get(k, float("nan")) for k in names]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar([x.upper() for x in names], values, color=["#566573", "#2471a3", "#117864", "#b7950b", "#922b21"])
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Two-Stage Op Amp DC Operating Point")
    ax.set_ylim(0, max(1.9, np.nanmax(values) * 1.15))
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / "opamp_dc_nodes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> opamp_dc_nodes.png")
