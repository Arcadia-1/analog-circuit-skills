#!/usr/bin/env python3
"""
run_cout_sweep.py
=================
Sweep C_OUT (output decoupling capacitor) and measure PM / GBW.

C_OUT sets the dominant output pole: fp = 1 / (2π·R_LOAD·C_OUT)
Larger C_OUT → lower dominant pole → GBW decreases → PM may improve or
degrade depending on where other poles/zeros fall relative to GBW.

Usage
-----
  cd LDO/scripts/
  python run_cout_sweep.py

Output
------
  WORK/plots/ldo_sweep_cout.png
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

# C_OUT sweep: 100 nF → 10 µF (logarithmically spaced)
COUT_VALS = [100e-9, 220e-9, 470e-9, 1e-6, 2.2e-6, 4.7e-6, 10e-6]   # F
NOMINAL   = ldo.C_OUT   # 1 µF

PNG = PLOT_DIR / "ldo_sweep_cout.png"


def main():
    print("=== C_OUT Sweep (PM / GBW vs C_OUT) ===")
    orig = ldo.C_OUT
    results = []

    for c in COUT_VALS:
        ldo.C_OUT = c
        fp_khz = 1 / (2 * np.pi * ldo.R_LOAD_DEFAULT * c) / 1e3
        print(f"\n  C_OUT = {c*1e6:.3f} µF   (fp ≈ {fp_khz:.2f} kHz)", flush=True)
        try:
            res = simulate_ac()
            m   = res["metrics"]
            pm  = m.get("phase_margin_deg", float("nan"))
            gbw = m.get("gbw_hz", float("nan"))
        except Exception as e:
            print(f"  WARN: sim failed ({e})")
            pm, gbw = float("nan"), float("nan")
        results.append((c, pm, gbw, fp_khz))

    ldo.C_OUT = orig   # restore

    _plot(results)


def _plot(results):
    c_uf_arr = np.array([x[0] for x in results]) * 1e6
    pm_arr   = np.array([x[1] for x in results])
    gbw_arr  = np.array([x[2] for x in results]) / 1e3   # kHz
    fp_arr   = np.array([x[3] for x in results])

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    fig.suptitle(f"LDO Stability Sweep: C_OUT\n"
                 f"(R_COMP={ldo.R_COMP} Ω  C_COMP={ldo.C_COMP*1e12:.0f} pF  "
                 f"R_LOAD={ldo.R_LOAD_DEFAULT} Ω)", fontsize=11)

    ax = axes[0]
    ax.semilogx(c_uf_arr, pm_arr, "o-", color="#1a7abf", lw=2, ms=6,
                label="Phase Margin")
    ax.axvline(NOMINAL * 1e6, color="#e07b00", lw=1.2, ls="--",
               label=f"Nominal {NOMINAL*1e6:.1f} µF")
    ax.axhline(45, color="#888888", lw=1, ls=":", label="45° target")
    ax.axhline(60, color="#aaaaaa", lw=1, ls=":", label="60° target")
    ax.set_ylabel("Phase Margin (°)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.25)
    ax.set_ylim(bottom=0)

    ax2 = axes[1]
    ax2.semilogx(c_uf_arr, gbw_arr, "s-", color="#e84141", lw=2, ms=6,
                 label="GBW")
    ax2.axvline(NOMINAL * 1e6, color="#e07b00", lw=1.2, ls="--",
                label=f"Nominal {NOMINAL*1e6:.1f} µF")
    ax2.set_xlabel("C_OUT (µF)", fontsize=10)
    ax2.set_ylabel("GBW (kHz)", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, which="both", alpha=0.25)

    # Secondary top axis: output pole frequency
    ax_top = axes[0].twiny()
    ax_top.set_xscale("log")
    ax_top.set_xlim(axes[0].get_xlim())
    ax_top.set_xticks(c_uf_arr)
    ax_top.set_xticklabels([f"{fp:.2f} kHz" for fp in fp_arr],
                            rotation=30, fontsize=7)
    ax_top.set_xlabel("Output pole fp = 1/(2π·R_LOAD·C_OUT)", fontsize=8)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved -> {PNG.name}")

    print("\n  C_OUT (µF)   fp (kHz)   PM (°)   GBW (kHz)")
    print("  " + "-" * 47)
    for c_uf, pm, gbw_khz, fp in zip(c_uf_arr,
                                      [x[1] for x in results],
                                      gbw_arr,
                                      fp_arr):
        flag = " ← nominal" if abs(c_uf - NOMINAL * 1e6) < 0.01 else ""
        print(f"  {c_uf:10.3f}   {fp:8.2f}   {pm:6.1f}   {gbw_khz:8.1f}{flag}")


if __name__ == "__main__":
    main()
