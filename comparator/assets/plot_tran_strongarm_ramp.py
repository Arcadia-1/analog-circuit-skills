#!/usr/bin/env python3
"""plot_tran_strongarm_ramp.py — Ramp input transient figure (2-panel)."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

RAMP_PNG = PLOT_DIR / "strongarm_ramp.png"

C_OUTP = "#1a7abf"
C_INP  = "#e84141"


def plot_ramp(ramp, params):
    """
    Two-panel ramp figure (shared x-axis):
      Top    : INP - INN (mV) — clean ramp input
      Bottom : OUTP - OUTN (V) — comparator output
    """
    if ramp is None or ramp.get("time") is None:
        print("  WARN: no ramp data to plot")
        return

    t_ns = ramp["time"] * 1e9
    vout = ramp.get("vout_diff")
    vin  = ramp.get("vin_diff")
    VDD  = params["VDD"]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 6), sharex=True,
        gridspec_kw={"height_ratios": [1, 2]},
    )
    fig.suptitle(
        f"StrongArm Comparator — Ramp Input Transient\n"
        f"{params['L_NM']}nm PTM HP, VDD={VDD}V, CLK=1GHz, "
        f"{params['RAMP_NCYC']} cycles",
        fontsize=12,
    )

    # Top: input ramp
    if vin is not None:
        ax_top.plot(t_ns, vin, color=C_INP, lw=1.2, label="INP $-$ INN")
    ax_top.axhline(0, color="gray", lw=0.6, ls=":")
    ax_top.set_ylabel("INP $-$ INN  (mV)", fontsize=9)
    ax_top.legend(fontsize=8, loc="upper left")
    ax_top.grid(True, alpha=0.25)
    ax_top.set_title("Differential Input (clean ramp)", fontsize=9)

    # Bottom: output
    if vout is not None:
        ax_bot.plot(t_ns, vout, color=C_OUTP, lw=0.8, alpha=0.85, label="OUTP $-$ OUTN")
    ax_bot.axhline(0, color="gray", lw=0.6, ls=":")
    ax_bot.set_ylabel("OUTP $-$ OUTN  (V)", fontsize=9)
    ax_bot.set_ylim(-VDD * 1.2, VDD * 1.2)
    ax_bot.set_xlabel("Time (ns)", fontsize=9)
    ax_bot.legend(fontsize=8, loc="upper left")
    ax_bot.grid(True, alpha=0.25)
    ax_bot.set_title("Differential Output", fontsize=9)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(RAMP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {RAMP_PNG.name}")
