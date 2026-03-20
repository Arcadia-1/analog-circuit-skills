#!/usr/bin/env python3
"""plot_ldo_dc.py — 3-panel DC figure: op summary, line reg, load reg."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

DC_PNG = PLOT_DIR / "ldo_dc.png"

C_LINE = "#1a7abf"
C_LOAD = "#e84141"
C_REF  = "#888888"


def plot_dc(results):
    """2-panel plot: operating-point text, line regulation."""
    op       = results.get("op", {})
    line_reg = results.get("line_reg", {})
    params   = results.get("params", {})

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle(
        f"PTM 180nm LDO — DC Analysis\n"
        f"VIN_nom={params.get('VIN_NOM', '?')}V, "
        f"VOUT_target={params.get('VOUT_NOM', '?')}V, "
        f"VREF={params.get('VREF_NOM', '?')}V, "
        f"R_load={params.get('R_LOAD', '?')}Ω",
        fontsize=11,
    )

    # ── Panel 0: Operating-point summary ──────────────────────────────────────
    ax = axes[0]
    ax.axis("off")
    vout = op.get("vout", float("nan"))
    vin  = op.get("vin",  float("nan"))
    vref = op.get("vref", float("nan"))
    vdrop = vin - vout

    line_vout = line_reg.get("vout_arr")
    line_vin  = line_reg.get("vin_arr")

    linereg_str = "n/a"
    if line_vin is not None and line_vout is not None and len(line_vin) > 1:
        dv = (line_vout[-1] - line_vout[0]) * 1e3
        dvin = line_vin[-1] - line_vin[0]
        linereg_str = f"{dv/dvin:.2f} mV/V"

    summary = (
        f"Operating Point\n"
        f"───────────────────\n"
        f"Vout    = {vout*1e3:.2f} mV\n"
        f"Vin     = {vin:.2f} V\n"
        f"Vref    = {vref:.3f} V\n"
        f"Dropout = {vdrop*1e3:.1f} mV\n\n"
        f"Line Regulation\n"
        f"───────────────────\n"
        f"ΔVout/ΔVin = {linereg_str}"
    )
    ax.text(0.05, 0.95, summary, transform=ax.transAxes,
            fontsize=10, family="monospace",
            verticalalignment="top", bbox=dict(boxstyle="round", fc="lightyellow", alpha=0.8))
    ax.set_title("DC Summary", fontsize=10)

    # ── Panel 1: Line regulation ───────────────────────────────────────────────
    ax = axes[1]
    if line_vin is not None and line_vout is not None:
        ax.plot(line_vin, line_vout * 1e3, color=C_LINE, lw=2, label="Vout")
        ax.axhline(params.get("VOUT_NOM", 1.8) * 1e3, color=C_REF,
                   lw=1, ls="--", label=f"Target {params.get('VOUT_NOM','?')}V")
        # Mark VIN_NOM operating point
        vin_nom = params.get("VIN_NOM", 2.3)
        if float(line_vin[0]) <= vin_nom <= float(line_vin[-1]):
            vout_nom_mv = float(np.interp(vin_nom, line_vin, line_vout)) * 1e3
            ax.plot(vin_nom, vout_nom_mv, "o", color=C_LINE, ms=6, zorder=5)
            ax.annotate(
                f"({vin_nom} V, {vout_nom_mv:.1f} mV)",
                xy=(vin_nom, vout_nom_mv),
                xytext=(vin_nom + 0.35, vout_nom_mv - 30),
                fontsize=8.5, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LINE, lw=0.8, alpha=0.6),
            )
        ax.set_xlabel("VIN (V)", fontsize=9)
        ax.set_ylabel("VOUT (mV)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.25)
    ax.set_title("Line Regulation (VIN Sweep)", fontsize=10)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DC_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {DC_PNG.name}")
