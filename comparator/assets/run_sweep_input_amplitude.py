#!/usr/bin/env python3
"""
run_sweep_input_amplitude.py
============================
Entry point: StrongArm input amplitude vs decision time.

Usage
-----
  cd H:/analog-circuit-skills/WORK/
  python run_sweep_input_amplitude.py

Output
------
  WORK/plots/sweep_input_amplitude.png
  WORK/logs/input_amplitude_report.txt
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "comparator" / "assets"))

from ngspice_common import LOG_DIR
from simulate_sweep_input_amplitude import sweep_input_amplitude, N_AMPL, VIN_START, VIN_STOP
from plot_sweep_input_amplitude import plot_input_amplitude

if __name__ == "__main__":
    results = sweep_input_amplitude()

    # Text report
    rpt = LOG_DIR / "input_amplitude_report.txt"
    with open(rpt, "w", encoding="utf-8") as f:
        f.write("StrongArm: Input Amplitude vs Tcmp\n")
        f.write(f"  {N_AMPL} points, Vin_diff = {VIN_START:.0e} – {VIN_STOP:.0e} V (log-spaced)\n\n")
        f.write(f"{'Vin_diff (mV)':>16}  {'Tcmp (ps)':>12}  {'Resolved':>10}\n")
        f.write("-" * 44 + "\n")
        for r in results:
            tcmp_str = f"{r['tcmp_ps']:.1f}" if r["resolved"] else "  (metastable)"
            f.write(f"  {r['vin_mv']:>14.6f}  {tcmp_str:>12}  {str(r['resolved']):>10}\n")
    print(f"  Report -> {rpt}")

    plot_input_amplitude(results)
    print("\n  Done. See WORK/plots/sweep_input_amplitude.png")
