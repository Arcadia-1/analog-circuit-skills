#!/usr/bin/env python3
"""
run_sweep_noise_bw.py
=====================
Entry point: StrongArm noise BW vs sigma_n sweep.

Usage
-----
  cd H:/analog-circuit-skills/WORK/
  python run_sweep_noise_bw.py

Output
------
  WORK/plots/sweep_noise_bw.png
  WORK/logs/noise_bw_report.txt

Note
----
High-BW points (short NT) are slower: each 10× increase in BW adds ~10× more
internal timesteps.  Expect ~30–120s total depending on CPU speed.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "comparator" / "assets"))

from ngspice_common import LOG_DIR
from simulate_sweep_noise_bw import (
    sweep_noise_bw, N_BW, BW_VALS, NT_VALS, NCYC_VALS, VIN_MV_VALS, SWEEP_TSTEP,
)
from plot_sweep_noise_bw import plot_noise_bw

if __name__ == "__main__":
    results = sweep_noise_bw()
    wall_s  = results[0].get("wall_s", float("nan")) if results else float("nan")

    # Text report
    rpt = LOG_DIR / "noise_bw_report.txt"
    with open(rpt, "w", encoding="utf-8") as f:
        f.write("StrongArm: Noise BW vs sigma_n\n")
        f.write(f"  {N_BW} BW points, {len(VIN_MV_VALS)} Vin levels each\n")
        f.write(f"  tstep={SWEEP_TSTEP*1e12:.0f}ps, adaptive NCYC\n")
        f.write(f"  Total wall time: {wall_s:.1f}s\n\n")
        f.write(f"{'BW (GHz)':>10}  {'NT (ps)':>8}  {'NCYC':>6}  "
                f"{'sigma_n (µV)':>14}  {'mu (µV)':>10}  {'fit_ok':>8}\n")
        f.write("-" * 66 + "\n")
        for r, ncyc in zip(results, NCYC_VALS):
            f.write(f"  {r['bw_ghz']:>8.1f}  {r['nt_ps']:>8.0f}  {ncyc:>6}  "
                    f"{r['sigma_uv']:>14.1f}  {r['mu_uv']:>10.1f}  "
                    f"{str(r['fit_ok']):>8}\n")
    print(f"  Report -> {rpt}")

    plot_noise_bw(results, wall_s=wall_s)
    print(f"\n  Done in {wall_s:.1f}s. See WORK/plots/sweep_noise_bw.png")
