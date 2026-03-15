#!/usr/bin/env python3
"""
plot_tran_strongarm_comp.py
===========================
Plotting routines for StrongArm comparator simulation results.

Produces three standalone PNG files:
  plots/strongarm_waveform.png  — 4-panel transition waveform (all internal nodes)
  plots/strongarm_noise.png     — Transfer curve: P(1) vs Vin, Gaussian CDF fit
  plots/strongarm_ramp.png      — 2-panel ramp: scatter + time trace

Public API
----------
plot_all(results, fom=None)
    results : dict from simulate_tran_strongarm_comp.simulate_all()
    fom     : dict from compute_fom() (optional, for annotations)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import norm

from ngspice_common import PLOT_DIR
from comparator_common import NOISE_VIN_MV

WAVE_PNG  = PLOT_DIR / "strongarm_waveform.png"
NOISE_PNG = PLOT_DIR / "strongarm_noise.png"
RAMP_PNG  = PLOT_DIR / "strongarm_ramp.png"

# Colours
C_CLK    = "#555555"
C_INP    = "#1a7abf"
C_INN    = "#e84141"
C_VXP    = "#1a7abf"
C_VXN    = "#e84141"
C_VLP    = "#2ca02c"
C_VLN    = "#d62728"
C_OUTP   = "#1a7abf"
C_OUTN   = "#e84141"
C_MEAS   = "#e65100"   # measured P(1) points
C_FIT    = "#1a7abf"   # fitted CDF curve
C_RESID  = "#7b1fa2"   # residuals


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: Transition waveform (testbench_cmp_tran)
# ─────────────────────────────────────────────────────────────────────────────
def plot_waveform(wave, params):
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

    # Panel 1: CLK + INP, INN
    ax = axes[0]
    if wave["clk"] is not None:
        ax.plot(t_ns, wave["clk"], color=C_CLK, lw=1.5, label="CLK", zorder=3)
    if wave["inp"] is not None:
        inp_mv = (np.array(wave["inp"]) - params["VCM"]) * 1e3
        inn_mv = (np.array(wave["inn"]) - params["VCM"]) * 1e3
        ax2 = ax.twinx()
        ax2.plot(t_ns, inp_mv, color=C_INP, lw=1.2, ls="--", label="INP-VCM")
        ax2.plot(t_ns, inn_mv, color=C_INN, lw=1.2, ls="--", label="INN-VCM")
        ax2.set_ylabel("Input offset (mV)", fontsize=9)
        ax2.legend(loc="upper right", fontsize=8, ncol=2)
        ax2.set_ylim(-3, 3)
    ax.set_ylabel("CLK (V)", fontsize=9)
    ax.set_ylim(-0.1, VDD * 1.15)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_title("Clock & Differential Input", fontsize=9)

    # Panel 2: Integration nodes VXP, VXN
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

    # Panel 3: Latch nodes VLP, VLN
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

    # Panel 4: Digital outputs OUTP, OUTN
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


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Single-point probit noise result
# ─────────────────────────────────────────────────────────────────────────────
def plot_noise(noise_pt, params, fom=None):
    """Single-point probit: Gaussian PDF + CDF with measurement point."""
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

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        f"StrongArm Comparator — Noise Extraction (Single-Point Probit)\n"
        f"{params['L_NM']}nm PTM HP, VDD={params['VDD']}V, CLK=1GHz, "
        f"{ncyc} cycles  |  "
        f"Noise BW={params.get('NOISE_BW_GHZ', '?'):.0f} GHz",
        fontsize=12,
    )

    # ── Left: Gaussian PDF ───────────────────────────────────────────────────
    ax0 = axes[0]
    pdf = norm.pdf(x_mv * 1e-3, 0, sigma_v) * 1e-3
    ax0.plot(x_mv, pdf, color=C_FIT, lw=2,
             label=f"N(0, σ²),  σ={sigma_uv:.0f} µV")
    ax0.axvline(0,       color="gray", lw=0.8, ls="--")
    ax0.axvline( vin_mv, color=C_MEAS, lw=1.5, ls="--",
                label=f"k = {vin_mv:+.2f} mV")
    x_shade = np.linspace(x_mv.min(), vin_mv, 300)
    ax0.fill_between(x_shade,
                     norm.pdf(x_shade * 1e-3, 0, sigma_v) * 1e-3,
                     alpha=0.15, color=C_FIT,
                     label=f"P(noise < k) = {p1*100:.1f}%")
    ann = (f"σ_n = {sigma_uv:.0f} µV\n"
           f"k   = {vin_mv:.2f} mV\n"
           f"P(1)= {p1*100:.1f}%\n"
           f"N   = {ncyc} cycles")
    ax0.text(0.97, 0.97, ann, transform=ax0.transAxes,
             fontsize=9, va="top", ha="right",
             bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=C_FIT, alpha=0.9))
    ax0.set_xlabel("Input-referred noise (mV)", fontsize=10)
    ax0.set_ylabel("Probability density (/mV)", fontsize=10)
    ax0.set_title("Input-Referred Noise PDF", fontsize=10)
    ax0.legend(fontsize=9)
    ax0.grid(True, alpha=0.3)

    # ── Right: CDF with measurement point ────────────────────────────────────
    ax1 = axes[1]
    cdf = norm.cdf(x_mv * 1e-3, 0, sigma_v) * 100
    ax1.plot(x_mv, cdf, color=C_FIT, lw=2,
             label=f"CDF  (σ={sigma_uv:.0f} µV)")
    ax1.scatter([vin_mv], [p1 * 100], s=80, color=C_MEAS, zorder=5,
                label=f"({vin_mv:.2f} mV,  {p1*100:.1f}%)")
    ax1.axhline(50,       color="gray", lw=0.7, ls=":")
    ax1.axvline(0,        color="gray", lw=0.7, ls=":")
    ax1.axvline(vin_mv,   color=C_MEAS, lw=1.0, ls="--", alpha=0.6)
    ax1.axhline(p1 * 100, color=C_MEAS, lw=1.0, ls="--", alpha=0.6)
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


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Ramp input analysis (testbench_cmp_ramp)
# ─────────────────────────────────────────────────────────────────────────────
def plot_ramp(ramp, params, fom=None):
    """
    Single-panel ramp figure: VIN_diff (mV, right axis) and
    VOUT_diff = OUTP−OUTN (V, left axis) vs time.
    """
    if ramp is None or ramp.get("time") is None:
        print("  WARN: no ramp data to plot")
        return

    t_ns     = ramp["time"] * 1e9
    vout     = ramp.get("vout_diff")
    vin      = ramp.get("vin_diff")
    VDD      = params["VDD"]

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.suptitle(
        f"StrongArm Comparator — Ramp Input Transient\n"
        f"{params['L_NM']}nm PTM HP, VDD={VDD}V, CLK=1GHz, "
        f"{params['RAMP_NCYC']} cycles",
        fontsize=12,
    )

    # Left axis: VOUT_diff = OUTP − OUTN
    if vout is not None:
        ax.plot(t_ns, vout, color=C_OUTP, lw=0.8, alpha=0.8, label="OUTP$-$OUTN")
    ax.axhline(0, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("OUTP $-$ OUTN  (V)", fontsize=10)
    ax.set_ylim(-VDD * 1.2, VDD * 1.2)
    ax.set_xlabel("Time (ns)", fontsize=10)
    ax.grid(True, alpha=0.25)

    # Right axis: VIN_diff = INP − INN
    if vin is not None:
        ax2 = ax.twinx()
        ax2.plot(t_ns, vin, color=C_INP, lw=1.2, ls="--", alpha=0.7, label="INP$-$INN")
        ax2.set_ylabel("INP $-$ INN  (mV)", fontsize=10, color=C_INP)
        ax2.tick_params(axis="y", labelcolor=C_INP)

    # Combined legend
    lines  = ax.get_lines()
    labels = [l.get_label() for l in lines]
    if vin is not None:
        lines2  = ax2.get_lines()
        labels2 = [l.get_label() for l in lines2]
        lines  += lines2
        labels += labels2
    ax.legend(lines, labels, fontsize=9, loc="upper left")

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(RAMP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {RAMP_PNG.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def plot_all(results, fom=None):
    """Create all three standalone figures from simulate_all() results."""
    params = results["params"]
    plot_waveform(results.get("wave"), params)
    plot_noise(results.get("noise_pt"), params, fom=fom)
    plot_ramp(results.get("ramp"), params, fom=fom)
    print(f"\n  Plots saved to: {PLOT_DIR}/")
    print(f"    {WAVE_PNG.name}")
    print(f"    {NOISE_PNG.name}")
    print(f"    {RAMP_PNG.name}")
