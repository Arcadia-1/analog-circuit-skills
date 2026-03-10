#!/usr/bin/env python3
"""
run_tran_strongarm_comp.py
==========================
Wrapper: runs all three StrongArm comparator simulations in parallel,
then generates all plots and the FOM report.

Each triplet can also be run independently:
  python run_tran_strongarm_wave.py     # waveform only
  python run_tran_strongarm_noise.py    # noise sweep + FOM only
  python run_tran_strongarm_ramp.py     # ramp only

Usage
-----
  cd comparator/assets/
  python run_tran_strongarm_comp.py

Outputs
-------
  plots/strongarm_waveform.png
  plots/strongarm_noise.png
  plots/strongarm_ramp.png
  logs/fom_report.txt
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))

from simulate_tran_strongarm_wave  import simulate_wave
from simulate_tran_strongarm_noise import simulate_noise, compute_fom, SWEEP_NCYC
from simulate_tran_strongarm_ramp  import simulate_ramp

from plot_tran_strongarm_wave  import plot_wave
from plot_tran_strongarm_noise import plot_noise
from plot_tran_strongarm_ramp  import plot_ramp


def main():
    t0 = time.perf_counter()

    # ── Run all three simulations in parallel ─────────────────────────────────
    print("=== StrongArm Comparator — Full Simulation Suite ===")
    print("  Running wave / noise / ramp in parallel ...\n")

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_wave  = pool.submit(simulate_wave)
        f_noise = pool.submit(simulate_noise)
        f_ramp  = pool.submit(simulate_ramp)

        wave_res  = f_wave.result()
        noise_res = f_noise.result()
        ramp_res  = f_ramp.result()

    t_sim = time.perf_counter() - t0

    # ── Compute FOM (from noise results) ──────────────────────────────────────
    fom = compute_fom(noise_res)

    # ── Plot ──────────────────────────────────────────────────────────────────
    plot_wave (wave_res["wave"],   wave_res["params"])
    plot_noise(noise_res["sweep"], noise_res["params"], fom=fom)
    plot_ramp (ramp_res["ramp"],   ramp_res["params"])

    # ── Print summary ─────────────────────────────────────────────────────────
    fit = fom["fit"]
    p   = noise_res["params"]

    noise_elapsed = [r["elapsed"] for r in noise_res["sweep"]]
    t_noise_wall  = max(noise_elapsed)
    t_noise_cpu   = sum(noise_elapsed)

    print("\n" + "=" * 62)
    print("  TRANSFER CURVE SWEEP  (P(1) vs Vin)")
    print("=" * 62)
    print(f"  {'Vin (mV)':>10}  {'HIGH':>6}  {'LOW':>6}  {'P(1) (%)':>10}")
    print("  " + "-" * 38)
    for r in noise_res["sweep"]:
        print(f"  {r['vin_mv']:>10.2f}  {r['count_1']:>6}  {r['count_0']:>6}  "
              f"{r['p1']*100:>10.1f}")
    print("=" * 62)

    print(f"\n  Noise wall time : {t_noise_wall:.1f}s  "
          f"(slowest of {len(noise_res['sweep'])} parallel points)")
    print(f"  Noise CPU time  : {t_noise_cpu:.1f}s  (sum over all points)")

    print("\n" + "=" * 62)
    print("  GAUSSIAN CDF FIT")
    print("=" * 62)
    print(f"  Fit converged : {'Yes' if fit['fit_ok'] else 'No'}")
    print(f"  sigma_n       : {fom['sigma_uv']:.1f} uV  "
          f"(+/- {fit['perr'][1]*1e6:.1f} uV)  [input-referred noise RMS]")
    print(f"  mu (offset)   : {fom['mu_uv']:.1f} uV  "
          f"(+/- {fit['perr'][0]*1e6:.1f} uV)  [input offset voltage]")
    print("=" * 62)

    e_cycle_nj = fom['p_avg_uw'] / (p['FCLK'] / 1e9) * 1e-6

    print("\n" + "=" * 62)
    print("  PERFORMANCE METRICS")
    print("=" * 62)
    print(f"  Noise  sigma_n : {fom['sigma_uv']:.1f} uV  [input-referred RMS]")
    print(f"  Offset mu      : {fom['mu_uv']:.1f} uV  [input offset]")
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

    print(f"\n  Total wall time: {t_sim:.1f}s")
    print(f"  Report  -> logs/fom_report.txt")
    print(f"  Plots   -> plots/strongarm_{{waveform,noise,ramp}}.png\n")


if __name__ == "__main__":
    main()
