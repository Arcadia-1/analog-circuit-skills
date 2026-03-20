#!/usr/bin/env python3
"""plot_ldo_ac.py — 3-panel AC figure: PSRR, Zout, loop gain."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

AC_PNG = PLOT_DIR / "ldo_ac.png"

C_PSRR   = "#1a7abf"
C_ZOUT   = "#e84141"
C_LG_MAG = "#2ca02c"
C_LG_PH  = "#ff7f0e"
C_REF    = "#888888"


def _mark_freq(ax, freq_arr, val_arr, f_mark, color, unit, dy=4.0, fac=None):
    """Dot + '(f, val)' coordinate label at f_mark on a semilogx axes.
    fac: multiplicative y-offset for log y-axis; dy: additive for linear y-axis.
    """
    if freq_arr is None or val_arr is None:
        return
    if not (float(freq_arr[0]) <= f_mark <= float(freq_arr[-1])):
        return
    v = float(np.interp(f_mark, freq_arr, val_arr))
    ax.plot(f_mark, v, "o", color=color, ms=4.5, zorder=5)
    f_str = f"{int(f_mark / 1e3)} kHz" if f_mark >= 1e3 else f"{int(f_mark)} Hz"
    y_text = v * fac if fac is not None else v + dy
    ax.annotate(
        f"({f_str}, {v:.3g} {unit})",
        xy=(f_mark, v),
        xytext=(f_mark * 2.8, y_text),
        fontsize=7.5, color=color,
        arrowprops=dict(arrowstyle="-", color=color, lw=0.7, alpha=0.5),
    )


def plot_ac(results):
    """3-panel AC plot: PSRR, Zout, Loop Gain (magnitude + phase)."""
    psrr     = results.get("psrr", {})
    zout     = results.get("zout", {})
    lg       = results.get("loopgain", {})
    metrics  = results.get("metrics", {})
    params   = results.get("params", {})

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    gbw = metrics.get("gbw_hz", float("nan"))
    pm  = metrics.get("phase_margin_deg", float("nan"))
    psrr_dc = metrics.get("psrr_dc_db", float("nan"))

    fig.suptitle(
        f"PTM 180nm LDO — AC Analysis\n"
        f"VIN={params.get('VIN_NOM','?')}V, VOUT={params.get('VOUT_NOM','?')}V  |  "
        f"GBW={gbw/1e3:.1f} kHz, PM={pm:.1f}°, PSRR_DC={psrr_dc:.1f} dB"
        if not np.isnan(gbw) else
        f"PTM 180nm LDO — AC Analysis\n"
        f"VIN={params.get('VIN_NOM','?')}V, VOUT={params.get('VOUT_NOM','?')}V",
        fontsize=11,
    )

    # ── Panel 0: PSRR ─────────────────────────────────────────────────────────
    ax = axes[0]
    freq = psrr.get("freq")
    mag  = psrr.get("mag_db")
    if freq is not None and mag is not None:
        psrr_db = -mag
        ax.semilogx(freq, psrr_db, color=C_PSRR, lw=2, label="PSRR")
        ax.axhline(0, color=C_REF, lw=0.8, ls=":")
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("PSRR (dB)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.25)
        if not np.isnan(psrr_dc):
            ax.set_title(f"PSRR  [DC = {psrr_dc:.1f} dB]", fontsize=10)
        else:
            ax.set_title("Power Supply Rejection Ratio", fontsize=10)
        _mark_freq(ax, freq, psrr_db, 1e3,   C_PSRR, "dB", dy=4)
        _mark_freq(ax, freq, psrr_db, 100e3, C_PSRR, "dB", dy=4)
    else:
        ax.set_title("PSRR (no data)", fontsize=10)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    # ── Panel 1: Output impedance ─────────────────────────────────────────────
    ax = axes[1]
    freq_z = zout.get("freq")
    mag_z  = zout.get("mag_db")
    if freq_z is not None and mag_z is not None:
        ax.semilogx(freq_z, mag_z, color=C_ZOUT, lw=2, label="|Zout|")
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("Zout (dBΩ)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.25)
        ax.set_title("Output Impedance", fontsize=10)
        _mark_freq(ax, freq_z, mag_z, 1e3,   C_ZOUT, "dBΩ", dy=4)
        _mark_freq(ax, freq_z, mag_z, 100e3, C_ZOUT, "dBΩ", dy=4)
    else:
        ax.set_title("Zout (no data)", fontsize=10)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    # ── Panel 2: Loop gain magnitude + phase ──────────────────────────────────
    ax = axes[2]
    freq_lg = lg.get("freq")
    mag_lg  = lg.get("mag_db")
    ph_lg   = lg.get("phase_deg")

    if freq_lg is not None and mag_lg is not None:
        ax.semilogx(freq_lg, mag_lg, color=C_LG_MAG, lw=2, label="|T| (dB)")
        ax.axhline(0, color=C_REF, lw=1, ls="--", label="0 dB")
        if not np.isnan(gbw):
            ax.axvline(gbw, color=C_LG_MAG, lw=0.8, ls=":", alpha=0.6)
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("Magnitude (dB)", fontsize=9, color=C_LG_MAG)
        ax.tick_params(axis="y", labelcolor=C_LG_MAG)
        ax.grid(True, which="both", alpha=0.25)
        _mark_freq(ax, freq_lg, mag_lg, 1e3,   C_LG_MAG, "dB", dy=4)
        _mark_freq(ax, freq_lg, mag_lg, 100e3, C_LG_MAG, "dB", dy=4)

        if ph_lg is not None:
            ax2 = ax.twinx()
            # ph_lg = angle(T) in degrees; starts near 0° at DC for this LDO topology
            ax2.semilogx(freq_lg, ph_lg, color=C_LG_PH, lw=2,
                         ls="--", label="Phase(T) (°)")
            ax2.axhline(0,    color=C_LG_PH, lw=0.8, ls=":", alpha=0.5, label="0°")
            ax2.axhline(-180, color=C_REF,   lw=0.8, ls="--", alpha=0.5, label="−180°")
            if not np.isnan(pm):
                # Mark phase at GBW = pm - 180  (e.g. PM=50° → line at -130°)
                ax2.axhline(pm - 180, color=C_LG_PH, lw=0.8, ls=":", alpha=0.3)
            ax2.set_ylabel("Phase (°)", fontsize=9, color=C_LG_PH)
            ax2.tick_params(axis="y", labelcolor=C_LG_PH)
            # Accommodate unwrapped phase: typically stays above ~-270° for this LDO
            ph_valid = ph_lg[~np.isnan(ph_lg)] if ph_lg is not None else []
            ph_min = float(np.min(ph_valid)) if len(ph_valid) else -200
            ax2.set_ylim(min(ph_min - 20, -270), 45)
            lines2, labels2 = ax2.get_legend_handles_labels()
        else:
            lines2, labels2 = [], []

        lines1, labels1 = ax.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="lower left")

        title = f"Loop Gain"
        if not np.isnan(gbw):
            title += f"  [GBW={gbw/1e3:.1f} kHz, PM={pm:.1f}°]"
        ax.set_title(title, fontsize=10)
    else:
        ax.set_title("Loop Gain (no data)", fontsize=10)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(AC_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {AC_PNG.name}")
