#!/usr/bin/env python3
"""
run_theory_verification.py
==========================
Verify LDO loop-gain theory against ngspice AC simulation.

Checks
------
1. Dominant output pole   fp  = 1/(2π·R_LOAD·C_OUT)
2. Compensation zero      fz  = 1/(2π·R_COMP·C_COMP)
3. PSRR at 1 kHz and 100 kHz  (theory: PSRR ≈ 1 + |T(f)|)
4. Zout at 1 kHz and 100 kHz  (theory: Zout ≈ R_LOAD / (1 + |T(f)|))
5. GBW and Phase Margin

Usage
-----
  cd LDO/scripts/
  python run_theory_verification.py

Output
------
  WORK/plots/ldo_theory_verify.png
  WORK/logs/ldo_theory_verify.txt
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))

from simulate_ldo_ac import simulate_ac
import ldo_common as ldo
from ngspice_common import PLOT_DIR, LOG_DIR

PNG = PLOT_DIR / "ldo_theory_verify.png"
TXT = LOG_DIR  / "ldo_theory_verify.txt"

# ── Spot frequencies for PSRR / Zout verification ────────────────────────────
F_SPOTS = [1e3, 10e3, 100e3]   # 1 kHz, 10 kHz, 100 kHz


def _interp_log(f_query, freq, values):
    """Log-frequency interpolation (safe, ignores NaN)."""
    valid = ~np.isnan(values) & (freq > 0)
    if valid.sum() < 2:
        return float("nan")
    return float(np.interp(np.log10(f_query),
                           np.log10(freq[valid]),
                           values[valid]))


def _find_fp(freq, T_mag_db):
    """Find first -3 dB frequency of loop gain."""
    valid = ~np.isnan(T_mag_db)
    f_v   = freq[valid]
    T_v   = T_mag_db[valid]
    dc    = T_v[0]
    tgt   = dc - 3.0
    for i in range(len(T_v) - 1):
        if T_v[i] >= tgt > T_v[i + 1]:
            frac = (tgt - T_v[i]) / (T_v[i + 1] - T_v[i])
            log_f = np.log10(f_v[i]) + frac * (np.log10(f_v[i + 1]) - np.log10(f_v[i]))
            return 10 ** log_f
    return float("nan")


def _find_fz(freq, T_phase_deg, fp_sim, gbw_hz):
    """
    Find compensation zero from loop-gain phase.

    The zero creates a local slowdown (least-negative slope) in the
    d(phase)/d(log f) curve, searched in the band [10·fp .. 0.8·GBW].
    """
    valid = ~np.isnan(T_phase_deg)
    f_v   = freq[valid]
    ph_v  = T_phase_deg[valid]
    if len(f_v) < 5:
        return float("nan")

    lo = max(fp_sim * 10, f_v[0])
    hi = min(gbw_hz * 0.8, f_v[-1])
    mask = (f_v >= lo) & (f_v <= hi)
    if mask.sum() < 5:
        return float("nan")

    f_s  = f_v[mask]
    ph_s = ph_v[mask]
    # d(phase)/d(log10 f) — positive peak = zero contribution
    dph  = np.gradient(ph_s, np.log10(f_s))
    idx  = int(np.argmax(dph))   # least-negative (closest to 0 or most positive)
    return float(f_s[idx])


def main():
    print("=== LDO Theory Verification ===\n")

    # ── Run AC simulation ─────────────────────────────────────────────────────
    res    = simulate_ac()
    lg     = res["loopgain"]
    psrr_d = res["psrr"]
    zout_d = res["zout"]
    m      = res["metrics"]

    freq_lg   = lg["freq"]
    T_mag     = lg["mag_db"]
    T_phase   = lg["phase_deg"]
    freq_psrr = psrr_d["freq"]
    psrr_mag  = psrr_d["mag_db"]   # dBV (negative → PSRR = -mag)
    freq_zout = zout_d["freq"]
    zout_mag  = zout_d["mag_db"]   # dBΩ

    gbw_hz = m.get("gbw_hz",           float("nan"))
    pm_deg = m.get("phase_margin_deg", float("nan"))
    dc_gain= m.get("dc_gain_db",       float("nan"))

    # ── Theoretical pole / zero ───────────────────────────────────────────────
    fz_theory  = 1 / (2 * np.pi * ldo.R_COMP  * ldo.C_COMP)   # compensation zero
    fp_theory  = 1 / (2 * np.pi * ldo.R_LOAD_DEFAULT * ldo.C_OUT)   # output dominant pole

    # ── Detected pole / zero from simulation ─────────────────────────────────
    fp_sim = _find_fp(freq_lg, T_mag) if freq_lg is not None else float("nan")
    fz_sim = _find_fz(freq_lg, T_phase, fp_sim, gbw_hz) \
             if freq_lg is not None else float("nan")

    # ── PSRR: simulation vs theory ────────────────────────────────────────────
    # Theory: PSRR(f) ≈ 20·log10(1 + |T(f)|)  (first-order closed-loop rejection)
    psrr_sim_vals    = {}
    psrr_theory_vals = {}
    for f in F_SPOTS:
        # simulation
        psrr_sim_vals[f] = -_interp_log(f, freq_psrr, psrr_mag)   # dB

        # theory from loop gain
        T_dB_at_f = _interp_log(f, freq_lg, T_mag)
        if not np.isnan(T_dB_at_f):
            T_lin = 10 ** (T_dB_at_f / 20)
            psrr_theory_vals[f] = 20 * np.log10(1 + T_lin)
        else:
            psrr_theory_vals[f] = float("nan")

    # ── Zout: simulation vs theory ────────────────────────────────────────────
    # Theory: Zout(f) ≈ R_LOAD / (1 + |T(f)|)   [closed-loop output impedance]
    zout_sim_vals    = {}
    zout_theory_vals = {}
    for f in F_SPOTS:
        # simulation (dBΩ)
        zout_sim_vals[f] = _interp_log(f, freq_zout, zout_mag)

        # theory
        T_dB_at_f = _interp_log(f, freq_lg, T_mag)
        if not np.isnan(T_dB_at_f):
            T_lin = 10 ** (T_dB_at_f / 20)
            zout_ohm = ldo.R_LOAD_DEFAULT / (1 + T_lin)
            zout_theory_vals[f] = 20 * np.log10(zout_ohm)
        else:
            zout_theory_vals[f] = float("nan")

    # ── Print report ──────────────────────────────────────────────────────────
    report = _build_report(
        fz_theory, fp_theory, fz_sim, fp_sim,
        gbw_hz, pm_deg, dc_gain,
        psrr_sim_vals, psrr_theory_vals,
        zout_sim_vals,  zout_theory_vals,
    )
    print(report)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TXT.write_text(report, encoding="utf-8")
    print(f"\n  Report -> {TXT.name}")

    # ── Plot ──────────────────────────────────────────────────────────────────
    _plot(freq_lg, T_mag, T_phase,
          freq_psrr, psrr_mag,
          freq_zout, zout_mag,
          fz_theory, fp_theory, fz_sim, fp_sim,
          gbw_hz, pm_deg,
          psrr_sim_vals, psrr_theory_vals,
          zout_sim_vals,  zout_theory_vals)


# ── Report builder ────────────────────────────────────────────────────────────
def _build_report(fz_th, fp_th, fz_sim, fp_sim,
                  gbw, pm, dc_gain,
                  psrr_sim, psrr_th, zout_sim, zout_th):
    nan = float("nan")

    def fmtf(v):
        if v != v: return "N/A"
        if v >= 1e6: return f"{v/1e6:.2f} MHz"
        if v >= 1e3: return f"{v/1e3:.2f} kHz"
        return f"{v:.1f} Hz"

    def fmtdb(v, unit="dB"):
        return f"{v:.1f} {unit}" if v == v else "N/A"

    def err(v_sim, v_th):
        if v_sim != v_sim or v_th != v_th or v_th == 0:
            return "N/A"
        return f"{(v_sim - v_th)/v_th * 100:+.1f}%"

    lines = [
        "=" * 65,
        "  LDO Loop-Gain Theory Verification",
        "=" * 65,
        "",
        "  Circuit parameters",
        f"    R_COMP = {ldo.R_COMP} Ohm    C_COMP = {ldo.C_COMP*1e12:.0f} pF",
        f"    C_OUT  = {ldo.C_OUT*1e6:.1f} uF      R_LOAD = {ldo.R_LOAD_DEFAULT} Ohm",
        "",
        "-" * 65,
        "  POLES & ZEROS",
        "-" * 65,
        f"  {'':25s}  {'Theory':>12}  {'Sim':>12}  {'Error':>8}",
        f"  {'Output dominant pole fp':25s}  {fmtf(fp_th):>12}  {fmtf(fp_sim):>12}  {err(fp_sim, fp_th):>8}",
        f"  {'Compensation zero fz':25s}  {fmtf(fz_th):>12}  {fmtf(fz_sim):>12}  {err(fz_sim, fz_th):>8}",
        f"  {'GBW (sim only)':25s}  {'N/A':>12}  {fmtf(gbw):>12}",
        f"  {'Phase margin (sim only)':25s}  {'N/A':>12}  {fmtdb(pm, 'deg'):>12}",
        f"  {'DC loop gain (sim only)':25s}  {'N/A':>12}  {fmtdb(dc_gain):>12}",
        "",
        "-" * 65,
        "  PSRR  [theory: PSRR(f) ~= 20*log10(1 + |T(f)|)]",
        "-" * 65,
        f"  {'Frequency':>10}  {'PSRR_sim':>10}  {'PSRR_theory':>12}  {'Diff':>8}",
    ]
    for f in F_SPOTS:
        s = psrr_sim.get(f, nan)
        t = psrr_th.get(f, nan)
        diff = f"{s - t:+.1f} dB" if s == s and t == t else "N/A"
        lines.append(
            f"  {fmtf(f):>10}  {fmtdb(s):>10}  {fmtdb(t):>12}  {diff:>8}"
        )
    lines += [
        "",
        "-" * 65,
        "  ZOUT  [theory: Zout(f) ~= R_LOAD / (1 + |T(f)|)]",
        "-" * 65,
        f"  {'Frequency':>10}  {'Zout_sim':>10}  {'Zout_theory':>12}  {'Diff':>8}",
    ]
    for f in F_SPOTS:
        s = zout_sim.get(f, nan)
        t = zout_th.get(f, nan)
        diff = f"{s - t:+.1f} dB" if s == s and t == t else "N/A"
        lines.append(
            f"  {fmtf(f):>10}  {fmtdb(s, 'dBOhm'):>10}  {fmtdb(t, 'dBOhm'):>12}  {diff:>8}"
        )
    lines += [
        "",
        "-" * 65,
        "  THEORY NOTES",
        "-" * 65,
        "  fp  = 1/(2*pi*R_LOAD*C_OUT)  — sets dominant output pole",
        f"      theory {fmtf(fp_th)}  vs  sim {fmtf(fp_sim)}",
        "  fz  = 1/(2*pi*R_COMP*C_COMP) — compensation zero for PM boost",
        f"      theory {fmtf(fz_th)}  vs  sim {fmtf(fz_sim)}",
        "  PSRR first-order model is PSRR ~= loop_gain in the loop BW.",
        "  Zout first-order model: Zout_CL = R_LOAD/(1+|T|) inside BW,",
        "      transitions to 1/(2*pi*f*C_OUT) beyond loop BW.",
        "=" * 65,
    ]
    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────
def _plot(freq_lg, T_mag, T_phase,
          freq_psrr, psrr_mag,
          freq_zout, zout_mag,
          fz_th, fp_th, fz_sim, fp_sim,
          gbw_hz, pm_deg,
          psrr_sim_vals, psrr_th_vals,
          zout_sim_vals,  zout_th_vals):

    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=False)
    fig.suptitle("LDO Theory Verification — Pole/Zero + PSRR + Zout\n"
                 f"R_COMP={ldo.R_COMP} Ohm  C_COMP={ldo.C_COMP*1e12:.0f} pF  "
                 f"C_OUT={ldo.C_OUT*1e6:.1f} uF  R_LOAD={ldo.R_LOAD_DEFAULT} Ohm",
                 fontsize=11)

    C_SIM  = "#1a7abf"
    C_TH   = "#e07b00"
    C_POLE = "#d62728"
    C_ZERO = "#2ca02c"
    C_SPOT = "#9467bd"

    # ── Panel 1: Loop gain Bode (mag + phase) ────────────────────────────────
    ax1 = axes[0]
    ax1p = ax1.twinx()

    if freq_lg is not None and T_mag is not None:
        valid = ~np.isnan(T_mag)
        ax1.semilogx(freq_lg[valid], T_mag[valid],
                     color=C_SIM, lw=2, label="|T| (dB)")
        ax1.axhline(0, color="#888888", lw=0.8, ls="--")

    if freq_lg is not None and T_phase is not None:
        vp = ~np.isnan(T_phase)
        ax1p.semilogx(freq_lg[vp], T_phase[vp],
                      color=C_SIM, lw=1.5, ls="--", alpha=0.7,
                      label="Phase(T) (deg)")
        ax1p.axhline(-180, color="#888888", lw=0.8, ls=":")

    # Theoretical pole / zero markers
    for f, label, color in [
        (fp_th,  f"fp_theory={fp_th/1e3:.1f} kHz", C_POLE),
        (fz_th,  f"fz_theory={fz_th/1e3:.0f} kHz", C_ZERO),
    ]:
        if not np.isnan(f):
            ax1.axvline(f, color=color, lw=1.5, ls=":",
                        label=label)
    for f, label, color in [
        (fp_sim, f"fp_sim={fp_sim/1e3:.1f} kHz" if fp_sim==fp_sim else "", C_POLE),
        (fz_sim, f"fz_sim={fz_sim/1e3:.0f} kHz"  if fz_sim==fz_sim else "", C_ZERO),
    ]:
        if not np.isnan(f) and label:
            ax1.axvline(f, color=color, lw=1.5, ls="--", alpha=0.6,
                        label=label)
    if not np.isnan(gbw_hz):
        ax1.axvline(gbw_hz, color="#888888", lw=1.2, ls="-.",
                    label=f"GBW={gbw_hz/1e3:.0f} kHz (PM={pm_deg:.1f} deg)")

    ax1.set_ylabel("|T| (dB)", fontsize=9, color=C_SIM)
    ax1p.set_ylabel("Phase(T) (deg)", fontsize=9, color=C_SIM, alpha=0.7)
    ax1.set_title("Loop Gain — Pole / Zero Verification", fontsize=10)
    lines1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(lines1, labels1, fontsize=7, loc="lower left", ncol=2)
    ax1.grid(True, which="both", alpha=0.2)

    # ── Panel 2: PSRR ────────────────────────────────────────────────────────
    ax2 = axes[1]
    if freq_psrr is not None and psrr_mag is not None:
        psrr_db = -psrr_mag   # flip sign: positive = good rejection
        ax2.semilogx(freq_psrr, psrr_db, color=C_SIM, lw=2,
                     label="PSRR sim")

    # Theory overlay: PSRR ~= 1 + |T(f)|
    if freq_lg is not None and T_mag is not None:
        valid = ~np.isnan(T_mag)
        T_lin   = 10 ** (T_mag[valid] / 20)
        psrr_th = 20 * np.log10(1 + T_lin)
        ax2.semilogx(freq_lg[valid], psrr_th,
                     color=C_TH, lw=1.5, ls="--",
                     label="PSRR theory ~= 20log10(1+|T|)")

    # Spot markers
    colors_spot = ["#9467bd", "#8c564b", "#e377c2"]
    for f, cs in zip(F_SPOTS, colors_spot):
        s = psrr_sim_vals.get(f, float("nan"))
        t = psrr_th_vals.get(f, float("nan"))
        if s == s:
            ax2.plot(f, s, "o", color=cs, ms=7, zorder=5)
            ax2.annotate(f"  sim {s:.1f} dB\n  th  {t:.1f} dB",
                         xy=(f, s), fontsize=7, color=cs,
                         xytext=(f * 1.5, s - 4))

    ax2.axvline(fz_th,  color=C_ZERO, lw=1.2, ls=":", alpha=0.7,
                label=f"fz={fz_th/1e3:.0f} kHz (theory)")
    ax2.axvline(gbw_hz, color="#888888", lw=1.0, ls="-.", alpha=0.7,
                label=f"GBW={gbw_hz/1e3:.0f} kHz")
    ax2.set_ylabel("PSRR (dB)", fontsize=9)
    ax2.set_title("PSRR: Simulation vs Theory", fontsize=10)
    ax2.legend(fontsize=7, loc="upper right")
    ax2.grid(True, which="both", alpha=0.2)
    ax2.set_ylim(bottom=0)

    # ── Panel 3: Zout ────────────────────────────────────────────────────────
    ax3 = axes[2]
    if freq_zout is not None and zout_mag is not None:
        ax3.semilogx(freq_zout, zout_mag, color=C_SIM, lw=2,
                     label="Zout sim (dBΩ)")

    # Theory overlay: Zout ~= R_LOAD / (1 + |T|)
    if freq_lg is not None and T_mag is not None:
        valid   = ~np.isnan(T_mag)
        T_lin   = 10 ** (T_mag[valid] / 20)
        zout_th = 20 * np.log10(ldo.R_LOAD_DEFAULT / (1 + T_lin))
        ax3.semilogx(freq_lg[valid], zout_th,
                     color=C_TH, lw=1.5, ls="--",
                     label=f"Zout theory ~= R_LOAD/(1+|T|)  [R_LOAD={ldo.R_LOAD_DEFAULT} Ohm]")

    for f, cs in zip(F_SPOTS, colors_spot):
        s = zout_sim_vals.get(f, float("nan"))
        t = zout_th_vals.get(f, float("nan"))
        if s == s:
            ax3.plot(f, s, "o", color=cs, ms=7, zorder=5)
            ax3.annotate(f"  sim {s:.1f} dBOhm\n  th  {t:.1f} dBOhm",
                         xy=(f, s), fontsize=7, color=cs,
                         xytext=(f * 1.5, s + 2))

    ax3.axvline(gbw_hz, color="#888888", lw=1.0, ls="-.", alpha=0.7,
                label=f"GBW={gbw_hz/1e3:.0f} kHz")
    ax3.set_ylabel("Zout (dBΩ)", fontsize=9)
    ax3.set_xlabel("Frequency (Hz)", fontsize=9)
    ax3.set_title("Output Impedance: Simulation vs Theory", fontsize=10)
    ax3.legend(fontsize=7, loc="upper right")
    ax3.grid(True, which="both", alpha=0.2)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved -> {PNG.name}")


if __name__ == "__main__":
    main()
