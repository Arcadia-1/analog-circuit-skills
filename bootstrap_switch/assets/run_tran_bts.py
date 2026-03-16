#!/usr/bin/env python3
"""
run_tran_bts.py — Master entry point for bootstrap switch skill.
Runs all simulations and generates all plots.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bootstrap_common import check_ngspice
from simulate_tran_bts_wave import simulate_wave
from simulate_tran_bts_ron import simulate_ron
from plot_tran_bts_wave import plot_wave
from plot_tran_bts_ron import plot_ron


def main():
    check_ngspice()
    t0 = time.perf_counter()

    print("\n" + "=" * 60)
    print("  Bootstrap Switch — Full Simulation Suite")
    print("=" * 60)

    # 1. Waveform
    wave_results = simulate_wave()
    plot_wave(wave_results)

    # 2. Ron comparison
    ron_results = simulate_ron()
    plot_ron(ron_results)

    wall = time.perf_counter() - t0

    # Summary
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    if wave_results.get("vboost") is not None:
        import numpy as np
        clk = wave_results["clk"]
        vboost = wave_results["vboost"]
        sampling = clk > wave_results["params"]["VDD"] / 2
        if np.any(sampling):
            vb_samp = vboost[sampling]
            print(f"  Bootstrap voltage (VGATE-VIN) during sampling:")
            print(f"    Mean:  {np.mean(vb_samp):.3f} V  (ideal: {wave_results['params']['VDD']:.1f} V)")
            print(f"    Min:   {np.min(vb_samp):.3f} V")
            print(f"    Max:   {np.max(vb_samp):.3f} V")

    print(f"\n  Total wall time: {wall:.1f}s")
    print("  Done.\n")


if __name__ == "__main__":
    main()
