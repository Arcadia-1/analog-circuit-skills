#!/usr/bin/env python3
"""
run_compare_wave.py
===================
StrongArm vs Miyahara waveform overlay — two Vin cases.

Runs 4 simulations in parallel (SA + Miyahara) × (1mV + 1µV),
then produces 4 PNG files:
  WORK/plots/compare_waveform_se_1mV.png
  WORK/plots/compare_waveform_diff_1mV.png
  WORK/plots/compare_waveform_se_1uV.png
  WORK/plots/compare_waveform_diff_1uV.png

Usage
-----
  cd H:/analog-circuit-skills/WORK/
  python run_compare_wave.py
"""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "comparator" / "assets"))

from simulate_compare_wave import _sim_strongarm, _sim_miyahara, _render_dut, WAVE_NCYC
from plot_compare_wave import plot_compare

VIN_CASES = [1.0, 1e-3]   # mV: 1mV and 1µV (= 0.001mV)

if __name__ == "__main__":
    print(f"\n=== Waveform Comparison: StrongArm vs Miyahara ===")
    print(f"  Cases: {[f'{v*1000:.0f}µV' if v < 1 else f'{v:.0f}mV' for v in VIN_CASES]}")
    print(f"  4 sims in parallel (SA + Miyahara) × (1mV + 1µV)\n")

    t0 = time.perf_counter()

    # Submit all 4 sims at once
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            (vin_mv, topo): pool.submit(fn, vin_mv)
            for vin_mv in VIN_CASES
            for topo, fn in [("sa", _sim_strongarm), ("miy", _sim_miyahara)]
        }
        results = {key: f.result() for key, f in futures.items()}

    wall = time.perf_counter() - t0
    print(f"\n  Sims done in {wall:.1f}s")

    # Plot both cases
    for vin_mv in VIN_CASES:
        sa  = results[(vin_mv, "sa")]
        miy = results[(vin_mv, "miy")]
        print(f"\n  Plotting Vin={vin_mv*1000:.3g}µV case ...")
        plot_compare(sa, miy, vin_mv=vin_mv)

    print("\n  Done. See WORK/plots/compare_waveform_*.png")
