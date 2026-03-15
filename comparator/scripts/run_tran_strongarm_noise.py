#!/usr/bin/env python3
"""
run_tran_strongarm_noise.py
===========================
Standalone entry point: single-point probit noise extraction (1000 cycles) + FOM.

Usage
-----
  cd comparator/scripts
  python run_tran_strongarm_noise.py

Outputs
-------
  plots/strongarm_noise.png
  logs/fom_report.txt
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_tran_strongarm_noise import simulate_noise, compute_fom, SWEEP_NCYC
from plot_tran_strongarm_noise import plot_noise


def main():
    results = simulate_noise()
    fom     = compute_fom(results)

    # plot_noise expects (noise_pt, params, fom=...)
    plot_noise(results["noise_pt"], results["params"], fom=fom)

    # ── Print summary ──────────────────────────────────────────────────────────
    noise_pt = results["noise_pt"]
    p        = results["params"]

    print("\n" + "=" * 62)
    print("  NOISE EXTRACTION  (single-point probit)")
    print("=" * 62)
    print(f"  Vin_fixed : {noise_pt['vin_mv']:.2f} mV")
    print(f"  Cycles    : {SWEEP_NCYC}")
    print(f"  COUNT_1   : {noise_pt['count_1']}")
    print(f"  P(1)      : {noise_pt['p1']*100:.1f}%")
    print(f"  sigma_n   : {noise_pt['sigma_uv']:.1f} uV  [input-referred RMS]")
    print("=" * 62)

    e_cycle_nj = fom['p_avg_uw'] / (p['FCLK'] / 1e9) * 1e-6

    print("\n" + "=" * 62)
    print("  PERFORMANCE METRICS")
    print("=" * 62)
    print(f"  Noise  sigma_n : {fom['sigma_uv']:.1f} uV  [input-referred RMS]")
    print(f"  Avg power      : {fom['p_avg_uw']:.2f} uW")
    print(f"  Energy/cycle   : {e_cycle_nj*1e6:.2f} fJ  =  {e_cycle_nj:.4e} nJ  (P / FCLK)")
    print(f"  Speed  Tcmp    : {fom['tcmp_ps']:.1f} ps  "
          f"(avg CLK->OUTP, Vin=+1mV, {SWEEP_NCYC} cycles)")
    print("-" * 62)
    print(f"  FOM1 = E_cycle x sigma^2   : {fom['fom1']:.4g} nJ*uV^2")
    print(f"       = {e_cycle_nj:.4e} nJ x {fom['sigma_uv']:.1f}^2 uV^2")
    print(f"  FOM2 = FOM1 x Tcmp         : {fom['fom2']:.4g} nJ*uV^2*ns")
    print(f"  Ref  (45nm, 1GHz)          : FOM1 ~ 8-30 nJ*uV^2")
    print("=" * 62)
    print(f"\n  Report -> logs/fom_report.txt\n")


if __name__ == "__main__":
    main()
