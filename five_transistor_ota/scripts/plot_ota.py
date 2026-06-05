#!/usr/bin/env python3
"""Plot helpers for five-transistor OTA simulations."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR


def plot_dc(result):
    dc = result["dc"]
    vin = dc["vin"]
    vout = dc["vout"]
    if vin is None or vout is None:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot((vin - result["params"]["VCM"]) * 1e3, vout, lw=2)
    ax.axvline(0, color="0.5", ls="--", lw=1)
    ax.set_xlabel("Input differential Vinp - Vinn (mV)")
    ax.set_ylabel("Output voltage (V)")
    ax.set_title("Five-Transistor OTA — DC Transfer")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / "ota_dc.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> ota_dc.png")


def plot_ac(result):
    ac = result["ac"]
    freq = ac["freq"]
    gain = ac["gain_db"]
    phase = ac["phase"]
    if freq is None or gain is None:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogx(freq, gain, lw=2, label="Gain")
    ax.axhline(0, color="0.5", ls="--", lw=1)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Gain (dB)")
    ax.grid(True, which="both", alpha=0.3)
    ax2 = ax.twinx()
    if phase is not None:
        ax2.semilogx(freq, phase, color="#e67e22", ls="--", lw=2, label="Phase")
    ax2.set_ylabel("Phase (deg)")
    m = result.get("metrics", {})
    ax.set_title(
        f"Five-Transistor OTA — AC  "
        f"Av0={m.get('dc_gain_db', float('nan')):.1f} dB, "
        f"UGB={m.get('ugb_hz', float('nan'))/1e6:.2f} MHz"
    )
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "ota_ac.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> ota_ac.png")


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
    ax.set_title("Five-Transistor OTA — Output Noise")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "ota_noise.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved -> ota_noise.png")

