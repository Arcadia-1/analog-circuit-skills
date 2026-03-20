#!/usr/bin/env python3
"""
run_ccomp_sweep.py
==================
Sweep C_COMP (compensation zero capacitor) and measure PM / GBW.

C_COMP sets the compensation zero: fz = 1 / (2π·R_COMP·C_COMP)
Smaller C_COMP → higher fz → less phase boost → lower PM.
Larger  C_COMP → lower  fz → more phase boost → higher PM (until other effects dominate).

Usage
-----
  cd LDO/scripts/
  python run_ccomp_sweep.py

Output
------
  WORK/plots/ldo_sweep_ccomp.png
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

# C_COMP sweep: 10 pF → 1 nF (logarithmically spaced)
CCOMP_VALS = [10e-12, 30e-12, 80e-12, 160e-12, 300e-12, 600e-12, 1e-9]   # F
NOMINAL    = ldo.C_COMP   # 160 pF

PNG = PLOT_DIR / "ldo_sweep_ccomp.png"


def main():
    print("=== C_COMP Sweep (PM / GBW vs C_COMP) ===")
    orig = ldo.C_COMP
    results = []

    for c in CCOMP_VALS:
        ldo.C_COMP = c
        fz_khz = 1 / (2 * np.pi * ldo.R_COMP * c) / 1e3
        print(f"\n  C_COMP = {c*1e12:.0f} pF   (fz ≈ {fz_khz:.1f} kHz)", flush=True)
        try:
            res = simulate_ac()
            m   = res["metrics"]
            pm  = m.get("phase_margin_deg", float("nan"))
            gbw = m.get("gbw_hz", float("nan"))
        except Exception as e:
            print(f"  WARN: sim failed ({e})")
            pm, gbw = float("nan"), float("nan")
        results.append((c, pm, gbw, fz_khz))

    ldo.C_COMP = orig   # restore

    _plot(results)


def _plot(results):
    c_pf_arr = np.array([x[0] for x in results]) * 1e12
    pm_arr   = np.array([x[1] for x in results])
    gbw_arr  = np.array([x[2] for x in results]) / 1e3   # kHz
    fz_arr   = np.array([x[3] for x in results])

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    fig.suptitle(f"LDO Compensation Sweep: C_COMP\n"
                 f"(R_COMP={ldo.R_COMP} Ω  C_OUT={ldo.C_OUT*1e6:.1f} µF  "
                 f"R_LOAD={ldo.R_LOAD_DEFAULT} Ω)", fontsize=11)

    ax = axes[0]
    ax.semilogx(c_pf_arr, pm_arr, "o-", color="#1a7abf", lw=2, ms=6,
                label="Phase Margin")
    ax.axvline(NOMINAL * 1e12, color="#e07b00", lw=1.2, ls="--",
               label=f"Nominal {NOMINAL*1e12:.0f} pF")
    ax.axhline(45, color="#888888", lw=1, ls=":", label="45° target")
    ax.axhline(60, color="#aaaaaa", lw=1, ls=":", label="60° target")
    ax.set_ylabel("Phase Margin (°)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.25)
    ax.set_ylim(bottom=0)

    ax2 = axes[1]
    ax2.semilogx(c_pf_arr, gbw_arr, "s-", color="#e84141", lw=2, ms=6,
                 label="GBW")
    ax2.axvline(NOMINAL * 1e12, color="#e07b00", lw=1.2, ls="--",
                label=f"Nominal {NOMINAL*1e12:.0f} pF")
    ax2.set_xlabel("C_COMP (pF)", fontsize=10)
    ax2.set_ylabel("GBW (kHz)", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, which="both", alpha=0.25)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved -> {PNG.name}")

    print("\n  C_COMP (pF)   fz (kHz)   PM (°)   GBW (kHz)")
    print("  " + "-" * 48)
    for c_pf, pm, gbw_khz, fz in zip(c_pf_arr,
                                      [x[1] for x in results],
                                      gbw_arr,
                                      fz_arr):
        flag = " ← nominal" if abs(c_pf - NOMINAL * 1e12) < 1 else ""
        print(f"  {c_pf:10.0f}   {fz:8.1f}   {pm:6.1f}   {gbw_khz:8.1f}{flag}")


if __name__ == "__main__":
    main()
