#!/usr/bin/env python3
"""
run_sweep_vcm.py
================
Entry point: StrongArm VCM vs noise sweep.
Runs 3 cases (100 / 200 / 300 cycles/point) sequentially.
After each simulation completes, the figure is saved immediately.

Noise extraction: single-point probit method —
  sigma_n = VIN_FIXED_MV / norm.ppf(P1)

Usage
-----
  cd H:/analog-circuit-skills/WORK/
  python run_sweep_vcm.py

Output
------
  WORK/plots/sweep_vcm_100cyc.png
  WORK/plots/sweep_vcm_200cyc.png
  WORK/plots/sweep_vcm_300cyc.png
  WORK/logs/vcm_noise_report_<N>cyc.txt
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "comparator" / "assets"))

from ngspice_common import LOG_DIR, PLOT_DIR
from simulate_sweep_vcm import (
    sweep_vcm, N_VCM, VCM_VALS, VIN_FIXED_MV,
    SWEEP_TSTEP, SWEEP_NOISE_NT, MAX_WORKERS,
)
from plot_sweep_vcm import plot_vcm

if __name__ == "__main__":
    for ncyc in [100, 200, 300]:
        print(f"\n{'='*60}")
        print(f"  Running: {ncyc} cycles/point")
        print(f"{'='*60}")

        results = sweep_vcm(ncyc=ncyc)
        wall_s  = results[0].get("wall_s", float("nan"))

        # Text report
        rpt = LOG_DIR / f"vcm_noise_report_{ncyc}cyc.txt"
        with open(rpt, "w", encoding="utf-8") as f:
            f.write(f"StrongArm: VCM vs Noise  ({ncyc} cycles/point)\n")
            f.write(f"  Method: single-point probit  Vin_fixed={VIN_FIXED_MV}mV\n")
            f.write(f"  {N_VCM} VCM points, {ncyc} cycles each, "
                    f"{SWEEP_TSTEP*1e12:.0f}ps step\n")
            f.write(f"  Noise BW: {1/(2*SWEEP_NOISE_NT)/1e9:.0f}GHz  "
                    f"(NT={SWEEP_NOISE_NT*1e12:.0f}ps)\n")
            f.write(f"  Max parallel workers: {MAX_WORKERS}\n")
            f.write(f"  Total wall time: {wall_s:.1f}s\n\n")
            f.write(f"{'VCM (V)':>10}  {'P(1) (%)':>10}  {'sigma_n (µV)':>14}\n")
            f.write("-" * 40 + "\n")
            for r in results:
                f.write(f"  {r['vcm']:>8.3f}  {r['p1']*100:>10.1f}  "
                        f"{r['sigma_uv']:>14.1f}\n")
        print(f"  Report -> {rpt}")

        out_png = PLOT_DIR / f"sweep_vcm_{ncyc}cyc.png"
        plot_vcm(results, wall_s=wall_s, n_cycles=ncyc, out_png=out_png)
        print(f"  Done in {wall_s:.1f}s.\n")
