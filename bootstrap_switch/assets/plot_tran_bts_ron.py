#!/usr/bin/env python3
"""
plot_tran_bts_ron.py
====================
Ron comparison figure: NMOS / PMOS / CMOS / Bootstrap switch.

plot_ron(results)          — single-node, one panel
plot_ron_multinode(nodes)  — three technology nodes side by side
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bootstrap_common import PLOT_DIR, VDD

OUT_PNG       = PLOT_DIR / "bts_ron_comparison.png"
OUT_PNG_MULTI = PLOT_DIR / "bts_ron_multinode.png"

C_NMOS  = "#e65100"
C_PMOS  = "#6a1b9a"
C_CMOS  = "#1a7abf"
C_BTS   = "#2e7d32"
RON_MAX = 200   # Ω — clip y-axis here


def _plot_one_panel(ax, results, show_ylabel=True):
    """Draw Ron vs VIN curves on a single axes object."""
    vin_pts  = results.get("vin_pts")
    if vin_pts is None or len(vin_pts) == 0:
        ax.text(0.5, 0.5, "no data", transform=ax.transAxes, ha="center")
        return

    p       = results["params"]
    node    = p.get("node_name", "180nm")
    vdd_val = p.get("VDD", VDD)
    l_nm    = p.get("L_NM", 180)

    def _clip(arr):
        """Return arr with values > RON_MAX replaced by NaN for plotting."""
        if arr is None or len(arr) == 0:
            return None
        a = np.array(arr, dtype=float)
        a[a > RON_MAX * 2] = np.nan   # extreme outliers → nan
        return a

    ron_nmos = _clip(results.get("ron_nmos"))
    ron_pmos = _clip(results.get("ron_pmos"))
    ron_cmos = _clip(results.get("ron_cmos"))
    ron_bts  = _clip(results.get("ron_bts"))

    kw_thin = dict(lw=1.2, ms=2.5, alpha=0.85)
    kw_cmos = dict(lw=2.0, ms=3, alpha=0.6)   # CMOS behind others

    # Draw CMOS first so NMOS/PMOS appear on top where they overlap
    if ron_cmos is not None:
        ax.plot(vin_pts / vdd_val, ron_cmos, "s--", color=C_CMOS, zorder=2,
                label=f"CMOS  W={p['W_sw']}µm L={l_nm}nm", **kw_cmos)
    if ron_nmos is not None:
        ax.plot(vin_pts / vdd_val, ron_nmos, "o-", color=C_NMOS, zorder=4,
                label=f"NMOS  W={p['W_sw']}µm L={l_nm}nm", **kw_thin)
    if ron_pmos is not None:
        ax.plot(vin_pts / vdd_val, ron_pmos, "D-", color=C_PMOS, zorder=4,
                label=f"PMOS  W={p['W_pmos_sw']}µm L={l_nm}nm", **kw_thin)
    if ron_bts is not None:
        ax.plot(vin_pts / vdd_val, ron_bts,  "^-", color=C_BTS, zorder=5,
                label="Bootstrap", lw=2.0, ms=4)

    ax.set_title(f"{node}  VDD={vdd_val}V", fontsize=9, fontweight="bold")
    ax.set_xlabel("VIN / VDD", fontsize=9)
    if show_ylabel:
        ax.set_ylabel("On-Resistance Ron (Ω)", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, RON_MAX)
    ax.legend(fontsize=7, loc="upper center")
    ax.grid(True, alpha=0.3)
    ax.text(0.98, 0.97, f">{RON_MAX}Ω clipped", transform=ax.transAxes,
            ha="right", va="top", fontsize=7, color="gray", style="italic")


def plot_ron(results):
    """Single-node Ron comparison figure."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    fig.suptitle(
        "On-Resistance Comparison — NMOS / PMOS / CMOS / Bootstrap Switch\n"
        f"180nm PTM, VDD={results['params'].get('VDD', VDD)}V, "
        f"W_sw={results['params']['W_sw']}µm, L={results['params']['L_NM']}nm",
        fontsize=10, fontweight="bold",
    )
    _plot_one_panel(ax, results, show_ylabel=True)
    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")


def plot_ron_multinode(node_results):
    """Three-panel figure: one panel per technology node, side by side."""
    n = len(node_results)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 5), sharey=True)
    if n == 1:
        axes = [axes]

    fig.suptitle(
        "On-Resistance: NMOS / PMOS / CMOS / Bootstrap Switch\n"
        "PTM models — 180nm / 45nm HP / 22nm HP",
        fontsize=11, fontweight="bold",
    )

    for i, (ax, res) in enumerate(zip(axes, node_results)):
        _plot_one_panel(ax, res, show_ylabel=(i == 0))

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG_MULTI, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG_MULTI}")
