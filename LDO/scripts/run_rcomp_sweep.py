#!/usr/bin/env python3
"""
run_rcomp_sweep.py
==================
Sweep R_COMP (compensation zero resistor) and measure PM / GBW.

R_COMP sets the compensation zero: fz = 1 / (2π·R_COMP·C_COMP)
Sweeping R_COMP shifts fz, which directly affects phase margin.

Usage
-----
  cd LDO/scripts/
  python run_rcomp_sweep.py

Output
------
  WORK/plots/ldo_sweep_rcomp.png
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))

import ldo_common as ldo
from simulate_ldo_ac import simulate_ac
from ngspice_common import PLOT_DIR

RCOMP_VALS = [200, 500, 1000, 2000, 5000, 10000, 20000]  # Ω
NOMINAL    = ldo.R_COMP   # 2000 Ω

PNG = PLOT_DIR / "ldo_sweep_rcomp.png"


def main():
    print("=== R_COMP Sweep (PM / GBW vs R_COMP) ===")
    orig = ldo.R_COMP
    results = []

    for r in RCOMP_VALS:
        ldo.R_COMP = r
        fz_khz = 1 / (2 * np.pi * r * ldo.C_COMP) / 1e3
        print(f"\n  R_COMP = {r} Ω   (fz ≈ {fz_khz:.1f} kHz)", flush=True)
        try:
            res = simulate_ac()
            m   = res["metrics"]
            pm  = m.get("phase_margin_deg", float("nan"))
            gbw = m.get("gbw_hz", float("nan"))
        except Exception as e:
            print(f"  WARN: sim failed ({e})")
            pm, gbw = float("nan"), float("nan")
        results.append((r, pm, gbw, fz_khz))

    ldo.R_COMP = orig   # restore

    _plot(results)


def _plot(results):
    r_arr   = np.array([x[0] for x in results])
    pm_arr  = np.array([x[1] for x in results])
    gbw_arr = np.array([x[2] for x in results]) / 1e3   # kHz
    fz_arr  = np.array([x[3] for x in results])

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    fig.suptitle(f"LDO Compensation Sweep: R_COMP\n"
                 f"(C_COMP={ldo.C_COMP*1e12:.0f} pF  C_OUT={ldo.C_OUT*1e6:.1f} µF  "
                 f"R_LOAD={ldo.R_LOAD_DEFAULT} Ω)", fontsize=11)

    # ── Phase margin ─────────────────────────────────────────────────────────
    ax = axes[0]
    ax.semilogx(r_arr, pm_arr, "o-", color="#1a7abf", lw=2, ms=6,
                label="Phase Margin")
    ax.axvline(NOMINAL, color="#e07b00", lw=1.2, ls="--",
               label=f"Nominal {NOMINAL} Ω")
    ax.axhline(45, color="#888888", lw=1, ls=":", label="45° target")
    ax.axhline(60, color="#aaaaaa", lw=1, ls=":", label="60° target")
    ax.set_ylabel("Phase Margin (°)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.25)
    ax.set_ylim(bottom=0)

    # ── GBW ──────────────────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.semilogx(r_arr, gbw_arr, "s-", color="#e84141", lw=2, ms=6,
                 label="GBW")
    ax2.axvline(NOMINAL, color="#e07b00", lw=1.2, ls="--",
                label=f"Nominal {NOMINAL} Ω")
    # Secondary x-axis: zero frequency fz
    ax2.set_xlabel("R_COMP (Ω)", fontsize=10)
    ax2.set_ylabel("GBW (kHz)", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, which="both", alpha=0.25)

    # Annotate fz on top axis
    ax_top = axes[0].twiny()
    ax_top.set_xscale("log")
    ax_top.set_xlim(axes[0].get_xlim())
    ax_top.set_xticks(r_arr)
    ax_top.set_xticklabels([f"{fz:.0f} kHz" for fz in fz_arr],
                            rotation=30, fontsize=7)
    ax_top.set_xlabel("Zero frequency fz = 1/(2π·R_COMP·C_COMP)", fontsize=8)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved -> {PNG.name}")

    # Print table
    print("\n  R_COMP (Ω)   fz (kHz)   PM (°)   GBW (kHz)")
    print("  " + "-" * 47)
    for r, pm, gbw_khz, fz in zip(r_arr,
                                   [x[1] for x in results],
                                   gbw_arr,
                                   fz_arr):
        flag = " ← nominal" if r == NOMINAL else ""
        print(f"  {r:10.0f}   {fz:8.1f}   {pm:6.1f}   {gbw_khz:8.1f}{flag}")


if __name__ == "__main__":
    main()
