#!/usr/bin/env python3
"""plot_tran_strongarm_noise.py — Single-point probit noise result figure."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import norm

from ngspice_common import PLOT_DIR
from comparator_common import NOISE_VIN_MV

NOISE_PNG = PLOT_DIR / "strongarm_noise.png"
C_DIST = "#1a7abf"
C_PT   = "#e65100"


def plot_noise(noise_pt, params, fom=None):
    """
    Single-panel plot for single-point probit noise extraction.
    Shows: Gaussian PDF N(0, sigma²), operating point (k, P1),
           and implied CDF transition.
    """
    if noise_pt is None:
        print("  WARN: no noise data to plot")
        return

    sigma_uv = noise_pt.get("sigma_uv", float("nan"))
    p1       = noise_pt.get("p1",       float("nan"))
    vin_mv   = noise_pt.get("vin_mv",   NOISE_VIN_MV)
    ncyc     = params.get("SWEEP_NCYC", "?")

    if np.isnan(sigma_uv):
        print("  WARN: sigma_uv is nan, skipping noise plot")
        return

    sigma_v = sigma_uv * 1e-6
    x_mv    = np.linspace(-4 * sigma_v * 1e3, 4 * sigma_v * 1e3, 500)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        f"StrongArm Comparator — Noise Extraction (Single-Point Probit)\n"
        f"{params['L_NM']}nm PTM HP, VDD={params['VDD']}V, CLK=1GHz, "
        f"{ncyc} cycles  |  "
        f"Noise BW={params.get('NOISE_BW_GHZ', '?'):.0f} GHz",
        fontsize=11,
    )

    # ── Left: Gaussian PDF of input-referred noise ───────────────────────────
    ax0 = axes[0]
    pdf = norm.pdf(x_mv * 1e-3, 0, sigma_v) * 1e-3   # scale to /mV
    ax0.plot(x_mv, pdf, color=C_DIST, lw=2, label=f"N(0, σ²),  σ={sigma_uv:.0f} µV")
    ax0.axvline(0,       color="gray",  lw=0.8, ls="--")
    ax0.axvline( vin_mv, color=C_PT,    lw=1.5, ls="--",
                label=f"k = {vin_mv:+.2f} mV (fixed input)")
    ax0.axvline(-vin_mv, color=C_PT,    lw=1.0, ls=":", alpha=0.5)

    # Shade P(noise < k) area
    x_shade = np.linspace(x_mv.min(), vin_mv, 300)
    y_shade = norm.pdf(x_shade * 1e-3, 0, sigma_v) * 1e-3
    ax0.fill_between(x_shade, y_shade, alpha=0.15, color=C_DIST,
                     label=f"P(noise < k) = P(1) = {p1*100:.1f}%")

    ann = (f"σ_n = {sigma_uv:.0f} µV\n"
           f"k   = {vin_mv:.2f} mV\n"
           f"P(1)= {p1*100:.1f}%\n"
           f"N   = {ncyc} cycles")
    ax0.text(0.97, 0.97, ann, transform=ax0.transAxes,
             fontsize=9, va="top", ha="right",
             bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=C_DIST, alpha=0.9))

    ax0.set_xlabel("Input-referred noise (mV)", fontsize=10)
    ax0.set_ylabel("Probability density (/mV)", fontsize=10)
    ax0.set_title("Input-Referred Noise PDF", fontsize=10)
    ax0.legend(fontsize=9)
    ax0.grid(True, alpha=0.3)

    # ── Right: Gaussian CDF with measurement point marked ───────────────────
    ax1 = axes[1]
    cdf = norm.cdf(x_mv * 1e-3, 0, sigma_v) * 100
    ax1.plot(x_mv, cdf, color=C_DIST, lw=2, label=f"CDF  (σ={sigma_uv:.0f} µV)")
    ax1.scatter([vin_mv], [p1 * 100], s=80, color=C_PT, zorder=5,
                label=f"Measurement: ({vin_mv:.2f} mV, {p1*100:.1f}%)")
    ax1.axhline(50,        color="gray", lw=0.7, ls=":")
    ax1.axvline(0,         color="gray", lw=0.7, ls=":")
    ax1.axvline(vin_mv,    color=C_PT,   lw=1.0, ls="--", alpha=0.6)
    ax1.axhline(p1 * 100,  color=C_PT,   lw=1.0, ls="--", alpha=0.6)

    if fom is not None and not np.isnan(fom.get("fom1", float("nan"))):
        fom_ann = (f"FOM1 = {fom['fom1']:.3g} nJ·µV²\n"
                   f"FOM2 = {fom['fom2']:.3g} nJ·µV²·ns")
        ax1.text(0.04, 0.96, fom_ann, transform=ax1.transAxes,
                 fontsize=8, va="top", ha="left",
                 bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.85))

    ax1.set_xlabel("Vin_diff (mV)", fontsize=10)
    ax1.set_ylabel("P(output = 1)  (%)", fontsize=10)
    ax1.set_title("Transfer Curve CDF", fontsize=10)
    ax1.set_ylim(-5, 105)
    ax1.legend(fontsize=9, loc="center right")
    ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(NOISE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {NOISE_PNG.name}")
