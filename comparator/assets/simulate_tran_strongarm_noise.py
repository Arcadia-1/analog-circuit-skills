#!/usr/bin/env python3
"""
simulate_tran_strongarm_noise.py
=================================
Noise sweep simulation: 13 Vin levels × 1000 cycles → P(1) statistics.
Also extracts power (Vin=0) and Tcmp (Vin=+1mV) for FOM calculation.
Testbench: testbench_cmp_tran_noise.cir.tmpl

Public API
----------
simulate_noise() -> dict
    'sweep'  : list of dicts {vin_mv, count_0, count_1, p1, p_avg_uw, tcmp_ps}
    'params' : circuit/sim parameters

compute_fom(noise_results) -> dict
    {sigma_uv, mu_uv, p_avg_uw, tcmp_ps, fom1, fom2, fit}
    Writes logs/fom_report.txt
"""

import os
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from ngspice_common import LOG_DIR, parse_wrdata, spath
from comparator_common import (
    VDD, VCM, FCLK, TCLK,
    circuit_params, render_dut, common_kw, run_netlist,
    sample_output, compute_tcmp, fit_transfer_curve,
)

SWEEP_VIN_MV = list(np.linspace(-1.5, 1.5, 13))   # mV, 13 equally spaced points
SWEEP_NCYC   = 1000
SWEEP_TSTOP  = SWEEP_NCYC * TCLK
SWEEP_TSTEP  = 50e-12    # 50 ps


def simulate_noise() -> dict:
    """Run 13-point Vin sweep, 1000 cycles each, in parallel."""
    print("\n=== Noise Sweep Simulation (13 points × 1000 cycles) ===")
    print(f"  Vin range: {SWEEP_VIN_MV[0]:.2f} to {SWEEP_VIN_MV[-1]:.2f} mV  |  "
          f"{SWEEP_NCYC} cycles each")

    dut_include, dut_tmp = render_dut()
    tasks = [(f"sw_{v:+.2f}", lambda v=v: _run_sweep_point(v, dut_include))
             for v in SWEEP_VIN_MV]

    t0 = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {name: pool.submit(fn) for name, fn in tasks}
            raw = {name: f.result() for name, f in futures.items()}
    finally:
        os.unlink(dut_tmp)

    wall = time.perf_counter() - t0
    print(f"\n  Wall time: {wall:.1f}s ({len(tasks)} points in parallel)")

    sweep = sorted(
        [raw[f"sw_{v:+.2f}"] for v in SWEEP_VIN_MV],
        key=lambda r: r["vin_mv"],
    )
    return {
        "sweep":  sweep,
        "params": circuit_params({"SWEEP_NCYC": SWEEP_NCYC}),
    }


def _run_sweep_point(vin_mv, dut_include):
    tag = f"sweep_vin{vin_mv:+.2f}mv"
    print(f"  [{tag}] starting ...", flush=True)
    t0  = time.perf_counter()

    vin  = vin_mv * 1e-3
    log  = LOG_DIR / f"strongarm_{tag}.log"
    out  = LOG_DIR / f"strongarm_{tag}_outp.txt"

    measure_power = (vin_mv == 0.0)
    if measure_power:
        ivdd_path = LOG_DIR / "strongarm_sweep_vin0_ivdd.txt"
        ivdd_cmd  = f"wrdata {spath(ivdd_path)} i(vvdd)"
    else:
        ivdd_path = None
        ivdd_cmd  = ""

    kw = dict(
        **common_kw(dut_include),
        vin_label = vin_mv,
        inp_src   = f"VINP_DC INP_DC 0 DC {VCM + vin/2:.10f}",
        inn_src   = f"VINN_DC INN_DC 0 DC {VCM - vin/2:.10f}",
        tstep     = f"{SWEEP_TSTEP:.4e}",
        tstop     = f"{SWEEP_TSTOP:.4e}",
        out_outp  = spath(out),
        ivdd_cmd  = ivdd_cmd,
    )
    rc = run_netlist("testbench_cmp_tran_noise.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0

    raw = parse_wrdata(out) if out.exists() else None
    count_1 = count_0 = 0
    time_arr = outp_arr = None
    samples_arr = None

    if raw is not None and len(raw) > 100:
        time_arr = raw[:, 0]
        outp_arr = raw[:, 1]
        samples  = sample_output(time_arr, outp_arr, SWEEP_NCYC)
        samples_arr = samples
        count_1  = int(np.sum(samples))
        count_0  = SWEEP_NCYC - count_1
    else:
        print(f"  [{tag}] WARNING: no usable data")

    p_avg_uw = float("nan")
    if measure_power and ivdd_path is not None and ivdd_path.exists():
        ivdd_raw = parse_wrdata(ivdd_path)
        if ivdd_raw is not None and len(ivdd_raw) > 100:
            p_avg_uw = VDD * np.mean(np.abs(ivdd_raw[:, 1])) * 1e6

    tcmp_ps = float("nan")
    if vin_mv == 1.0 and time_arr is not None:
        tcmp_ps = compute_tcmp(time_arr, outp_arr, SWEEP_NCYC)
        print(f"  [{tag}] Tcmp = {tcmp_ps:.1f} ps  (avg {SWEEP_NCYC} cycles)", flush=True)

    p1 = count_1 / SWEEP_NCYC
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s | "
          f"Vin={vin_mv:+.2f}mV -> {count_1}/{SWEEP_NCYC} HIGH  "
          f"P(1)={p1*100:.1f}%", flush=True)

    return {
        "vin_mv": vin_mv, "count_0": count_0, "count_1": count_1, "p1": p1,
        "p_avg_uw": p_avg_uw, "tcmp_ps": tcmp_ps,
        "rc": rc, "elapsed": elapsed,
        "samples": samples_arr,   # int array shape (SWEEP_NCYC,) or None
    }


# ─────────────────────────────────────────────────────────────────────────────
# FOM calculation
# ─────────────────────────────────────────────────────────────────────────────
def compute_fom(noise_results) -> dict:
    """
    Compute FOM from noise sweep results.

    FOM1 [nJ·µV²] = E_cycle [nJ] × sigma_n² [µV²]
    FOM2 [nJ·µV²·ns] = FOM1 × Tcmp [ns]
    """
    sweep  = noise_results["sweep"]
    params = noise_results["params"]

    fit      = fit_transfer_curve(sweep)
    sigma_uv = fit["sigma_uv"]
    mu_uv    = fit["mu_uv"]

    vin0     = next((r for r in sweep if r["vin_mv"] == 0.0), None)
    p_avg_uw = vin0["p_avg_uw"] if vin0 and not np.isnan(vin0.get("p_avg_uw", float("nan"))) else float("nan")

    vin1    = next((r for r in sweep if r["vin_mv"] == 1.0), None)
    tcmp_ps = vin1["tcmp_ps"] if vin1 and not np.isnan(vin1.get("tcmp_ps", float("nan"))) else float("nan")

    FCLK_GHZ = FCLK / 1e9
    fom1 = fom2 = float("nan")
    if not any(np.isnan([sigma_uv, p_avg_uw])):
        e_cycle_nj = p_avg_uw / FCLK_GHZ * 1e-6
        fom1 = e_cycle_nj * (sigma_uv ** 2)
    if not any(np.isnan([fom1, tcmp_ps])):
        fom2 = fom1 * (tcmp_ps / 1e3)

    # Write report
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "fom_report.txt"
    p = params

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  StrongArm Comparator -- Performance Report\n")
        f.write("=" * 60 + "\n\n")
        f.write("Circuit parameters\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Technology   : {p['L_NM']}nm PTM HP\n")
        f.write(f"  VDD          : {p['VDD']:.2f} V\n")
        f.write(f"  VCM          : {p['VCM']:.2f} V\n")
        f.write(f"  FCLK         : {p['FCLK']/1e9:.1f} GHz\n")
        f.write(f"  Noise BW     : {p['NOISE_BW_GHZ']:.0f} GHz\n")
        f.write(f"  Noise NA     : {p['NOISE_NA_UV']:.0f} uV per side\n")
        for dev, wval in p["W"].items():
            f.write(f"  W_{dev:<6}     : {wval:.1f} um\n")
        f.write("\n")
        f.write("Transfer curve sweep (P(1) vs Vin)\n")
        f.write("-" * 40 + "\n")
        f.write(f"  {'Vin (mV)':>10}  {'count_1':>8}  {'count_0':>8}  {'P(1) (%)':>10}\n")
        for r in sweep:
            f.write(f"  {r['vin_mv']:>10.2f}  {r['count_1']:>8d}  "
                    f"{r['count_0']:>8d}  {r['p1']*100:>10.1f}\n")
        f.write("\n")
        f.write("Gaussian CDF fit  [P(1) = Phi((Vin - mu) / sigma)]\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Fit converged: {'Yes' if fit['fit_ok'] else 'No'}\n")
        f.write(f"  Noise sigma  : {sigma_uv:.1f} uV  (+/- {fit['perr'][1]*1e6:.1f} uV)\n")
        f.write(f"  Offset mu    : {mu_uv:.1f} uV  (+/- {fit['perr'][0]*1e6:.1f} uV)\n")
        f.write("\n")
        f.write("Performance metrics\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Avg power : {p_avg_uw:.2f} uW  (Vin=0, {SWEEP_NCYC} cycles)\n")
        f.write(f"  Tcmp      : {tcmp_ps:.1f} ps  (avg CLK->OUTP, Vin=+1mV, {SWEEP_NCYC} cycles)\n")
        f.write("\n")
        f.write("Figure of Merit\n")
        f.write("-" * 40 + "\n")
        f.write(f"  FOM1 = E_cycle x sigma_n^2  : {fom1:.4g} nJ*uV^2\n")
        f.write(f"  FOM2 = FOM1 x Tcmp          : {fom2:.4g} nJ*uV^2*ns\n")
        f.write("\n")
        f.write("  Reference (45nm, 1GHz): FOM1 ~ 8-30 nJ*uV^2\n")
        f.write(f"\nReport: {log_path}\n")

    print(f"\n  FOM report -> {log_path}")
    return dict(
        sigma_uv=sigma_uv, mu_uv=mu_uv,
        p_avg_uw=p_avg_uw, tcmp_ps=tcmp_ps,
        fom1=fom1, fom2=fom2, fit=fit,
    )
