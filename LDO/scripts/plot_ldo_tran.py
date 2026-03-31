#!/usr/bin/env python3
"""plot_ldo_tran.py — 2-panel load-step transient response."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

TRAN_PNG = PLOT_DIR / "ldo_tran.png"

C_VOUT = "#1a7abf"
C_STEP = "#e84141"
C_ANN  = "#e07b00"


def plot_tran(results):
    """2-panel transient: VOUT waveform (top) + load current annotation (bottom)."""
    tran    = results.get("tran", {})
    metrics = results.get("metrics", {})
    params  = results.get("params", {})

    t    = tran.get("time")
    vout = tran.get("vout")

    iload_step = params.get("ILOAD_STEP", 0.1)
    r_idle     = params.get("R_IDLE", 1800)
    t_pre      = params.get("T_PRE", 10e-6)
    t_step_on  = params.get("T_STEP_ON", 50e-6)
    trise      = params.get("TRISE", 100e-9)

    vout_ss  = metrics.get("vout_ss_mv",       float("nan"))
    v_drop   = metrics.get("v_drop_mv",         float("nan"))
    v_over   = metrics.get("v_overshoot_mv",    float("nan"))
    load_reg = metrics.get("load_reg_tran_mv",  float("nan"))
    t_rec    = metrics.get("t_rec_us",          float("nan"))

    title_parts = [f"VIN={params.get('VIN_NOM','?')}V  VOUT={params.get('VOUT_NOM','?')}V",
                   f"Step: 0→{iload_step*1e3:.0f} mA"]
    if not np.isnan(v_drop):
        title_parts.append(f"V_drop={v_drop:.1f} mV")
    if not np.isnan(t_rec):
        title_parts.append(f"t_rec={t_rec:.2f} µs")
    if not np.isnan(v_over):
        title_parts.append(f"V_over={v_over:.1f} mV")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle("PTM 180nm LDO — Transient Load-Step Response\n" +
                 "  |  ".join(title_parts), fontsize=11)

    # ── Top: VOUT ────────────────────────────────────────────────────────────
    ax = axes[0]
    if t is not None and vout is not None:
        t_us = t * 1e6
        v_mv = vout * 1e3
        ax.plot(t_us, v_mv, color=C_VOUT, lw=1.8, label="VOUT")

        # Light-load SS reference
        if not np.isnan(vout_ss):
            ax.axhline(vout_ss, color="#888888", lw=1, ls="--",
                       label=f"SS (light) = {vout_ss:.1f} mV")

        # Heavy-load SS
        vout_heavy = metrics.get("vout_heavy_mv", float("nan"))
        if not np.isnan(vout_heavy):
            ax.axhline(vout_heavy, color="#aaaaaa", lw=1, ls=":",
                       label=f"SS (heavy) = {vout_heavy:.1f} mV")

        # Step markers
        t_pre_us = t_pre * 1e6
        t_end_us = (t_pre + t_step_on) * 1e6
        ax.axvline(t_pre_us, color=C_ANN, lw=1.0, ls="--", alpha=0.6)
        ax.axvline(t_end_us, color=C_ANN, lw=1.0, ls="--", alpha=0.6)

        # Annotate drop with double arrow — anchor at time of VOUT minimum
        if not np.isnan(v_drop) and not np.isnan(vout_ss):
            vout_min = metrics.get("vout_min_mv", vout_ss - v_drop)
            # Find time index of minimum during the load step
            mask_step = (t_us >= t_pre_us) & (t_us <= t_end_us)
            if mask_step.sum() > 0:
                idx_min = int(np.argmin(v_mv[mask_step]))
                t_min_us = float(t_us[mask_step][idx_min])
            else:
                t_min_us = t_pre_us
            x_ann = t_min_us + (t_end_us - t_pre_us) * 0.04
            ax.annotate("", xy=(x_ann, vout_min), xytext=(x_ann, vout_ss),
                        arrowprops=dict(arrowstyle="<->", color=C_ANN, lw=1.5))
            ax.text(x_ann + (t_end_us - t_pre_us) * 0.02,
                    (vout_min + vout_ss) / 2,
                    f"↕ {v_drop:.1f} mV", color=C_ANN, fontsize=8, va="center")

        # Annotate recovery
        if not np.isnan(t_rec):
            t_rec_mark = t_end_us + t_rec
            ax.annotate(f"t_rec = {t_rec:.2f} µs",
                        xy=(t_rec_mark, vout_ss),
                        xytext=(t_rec_mark + 2, vout_ss - v_drop * 0.4),
                        fontsize=8, color=C_ANN,
                        arrowprops=dict(arrowstyle="->", color=C_ANN, lw=1))

        ax.set_ylabel("VOUT (mV)", fontsize=10)
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(True, alpha=0.25)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes)

    # ── Bottom: Load current (reconstructed from pulse params) ───────────────
    ax2 = axes[1]
    if t is not None:
        t_us      = t * 1e6
        i_idle_ma = params.get("VOUT_NOM", 1.8) / r_idle * 1e3
        i_step_ma = iload_step * 1e3
        trise_us  = trise * 1e6
        t_pre_us  = t_pre * 1e6
        t_end_us  = (t_pre + t_step_on) * 1e6

        i_arr = np.full(len(t_us), i_idle_ma)
        mask_on = (t_us >= t_pre_us) & (t_us < t_end_us)
        i_arr[mask_on] = i_idle_ma + i_step_ma
        # Soften edges (very short ramp; linear interpolation over TRISE)
        for sign, t0_us in [(+1, t_pre_us), (-1, t_end_us)]:
            mask_ramp = (t_us >= t0_us) & (t_us < t0_us + trise_us)
            if mask_ramp.sum() > 0:
                frac = (t_us[mask_ramp] - t0_us) / max(trise_us, 1e-12)
                i_arr[mask_ramp] = (i_idle_ma +
                                    i_step_ma * (frac if sign > 0 else 1 - frac))

        ax2.plot(t_us, i_arr, color=C_STEP, lw=2, label="I_LOAD")
        ax2.set_ylabel("I_LOAD (mA)", fontsize=9)
        ax2.set_xlabel("Time (µs)", fontsize=10)
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.25)
        ax2.set_ylim(bottom=0)
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center",
                 transform=ax2.transAxes)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(TRAN_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {TRAN_PNG.name}")
