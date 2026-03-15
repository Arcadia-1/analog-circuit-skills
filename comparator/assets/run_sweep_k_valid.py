#!/usr/bin/env python3
"""
run_sweep_k_valid.py
====================
Validate the single-point probit noise extraction method.
Sweeps k (fixed differential input) at VCM=0.6V and plots sigma_n vs k.
If the method is correct, sigma_n should be flat across all k values.

Usage
-----
  cd H:/analog-circuit-skills/WORK/
  python run_sweep_k_valid.py

Output
------
  WORK/plots/sweep_k_valid.png
  WORK/logs/k_valid_report.txt
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "comparator" / "assets"))

from ngspice_common import LOG_DIR
from simulate_sweep_k_valid import sweep_k, K_MV_VALS, NCYC, VCM_FIXED, NOISE_NT
from plot_sweep_k_valid import plot_k_valid

if __name__ == "__main__":
    results = sweep_k()
    wall_s  = results[0].get("wall_s", float("nan"))

    rpt = LOG_DIR / "k_valid_report.txt"
    with open(rpt, "w", encoding="utf-8") as f:
        f.write("Single-Point Probit Validation: sigma_n vs k\n")
        f.write(f"  VCM={VCM_FIXED:.3f}V  |  {NCYC} cycles/point  |  "
                f"NT={NOISE_NT*1e12:.0f}ps  BW={1/(2*NOISE_NT)/1e9:.0f}GHz\n")
        f.write(f"  Total wall time: {wall_s:.1f}s\n\n")
        f.write(f"{'k (mV)':>10}  {'P(1) (%)':>10}  {'sigma_n (µV)':>14}\n")
        f.write("-" * 40 + "\n")
        for r in results:
            f.write(f"  {r['k_mv']:>8.3f}  {r['p1']*100:>10.1f}  "
                    f"{r['sigma_uv']:>14.1f}\n")
    print(f"  Report -> {rpt}")

    plot_k_valid(results, wall_s=wall_s)
    print(f"\n  Done in {wall_s:.1f}s. See WORK/plots/sweep_k_valid.png")
