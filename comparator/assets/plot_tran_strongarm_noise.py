#!/usr/bin/env python3
"""plot_tran_strongarm_noise.py — Transfer curve + Gaussian CDF fit figure."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import erfc

from ngspice_common import PLOT_DIR
from comparator_common import fit_transfer_curve

NOISE_PNG = PLOT_DIR / "strongarm_noise.png"

C_MEAS  = "#e65100"
C_FIT   = "#1a7abf"


def plot_noise(sweep, params, fom=None):
    """
    Two-panel noise figure:
      Left   : P(1) vs Vin scatter + fitted Gaussian CDF
      Right  : Residuals (measured - fitted)
    """
    if not sweep:
        print("  WARN: no sweep data to plot")
        return

    fit = fit_transfer_curve(sweep)
    vin_arr  = fit["vin_arr"] * 1e3        # V -> mV
    p1_meas  = fit["p1_arr"] * 100
    p1_fit   = fit["p1_fit"] * 100

    vin_dense = np.linspace(vin_arr.min() - 0.5, vin_arr.max() + 0.5, 400) * 1e-3
    p1_dense  = 0.5 * erfc(-(vin_dense - fit["mu_v"]) / (fit["sigma_v"] * np.sqrt(2))) * 100

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        f"StrongArm Comparator — Transfer Curve & Noise Extraction\n"
        f"{params['L_NM']}nm PTM HP, VDD={params['VDD']}V, CLK=1GHz, "
        f"{params['SWEEP_NCYC']} cycles/point, {len(sweep)} Vin levels, "
        f"Noise BW={params.get('NOISE_BW_GHZ', '?'):.0f} GHz",
        fontsize=11,
    )

    # ── Left: P(1) vs Vin ────────────────────────────────────────────────────
    ax0, ax1 = axes
    ax0.scatter(vin_arr, p1_meas, s=60, color=C_MEAS, zorder=5,
                label=f"Measured ({params['SWEEP_NCYC']} cycles each)")
    ax0.plot(vin_dense * 1e3, p1_dense, color=C_FIT, lw=2, label="Gaussian CDF fit")
    ax0.axhline(50, color="gray", lw=0.7, ls=":")
    ax0.axvline(fit["mu_uv"] / 1e3, color="gray", lw=0.7, ls=":")

    fit_status = "converged" if fit["fit_ok"] else "FAILED"
    ann = (
        f"Fit ({fit_status})\n"
        f"$\\sigma$ = {fit['sigma_uv']:.0f} $\\mu$V"
        f"  ($\\pm${fit['perr'][1]*1e6:.0f} $\\mu$V)\n"
        f"$\\mu$  = {fit['mu_uv']:.0f} $\\mu$V"
        f"  ($\\pm${fit['perr'][0]*1e6:.0f} $\\mu$V)"
    )
    ax0.text(0.04, 0.96, ann, transform=ax0.transAxes,
             fontsize=9, va="top", ha="left",
             bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=C_FIT, alpha=0.85))

    if fom is not None and not np.isnan(fom.get("fom1", float("nan"))):
        fom_ann = (
            f"FOM1 = {fom['fom1']:.3g} nJ·$\\mu$V$^2$\n"
            f"FOM2 = {fom['fom2']:.3g} nJ·$\\mu$V$^2$·ns"
        )
        ax0.text(0.96, 0.04, fom_ann, transform=ax0.transAxes,
                 fontsize=8, va="bottom", ha="right",
                 bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.85))

    ax0.set_xlabel("Vin_diff (mV)", fontsize=10)
    ax0.set_ylabel("P(output = 1)  (%)", fontsize=10)
    ax0.set_title("Transfer Curve: P(1) vs Vin", fontsize=10)
    ax0.set_ylim(-5, 105)
    ax0.legend(fontsize=9, loc="center right")
    ax0.grid(True, alpha=0.3)

    # ── Middle: Residuals ─────────────────────────────────────────────────────
    ax1 = axes[1]
    residuals = p1_meas - p1_fit
    ax1.bar(vin_arr, residuals, width=np.diff(vin_arr).min() * 0.6,
            color=[C_MEAS if r >= 0 else C_FIT for r in residuals], alpha=0.8)
    ax1.axhline(0, color="black", lw=0.8)
    ax1.set_xlabel("Vin_diff (mV)", fontsize=10)
    ax1.set_ylabel("Residual: measured - fit  (%)", fontsize=10)
    ax1.set_title("Fit Residuals", fontsize=10)
    ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(NOISE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {NOISE_PNG.name}")
