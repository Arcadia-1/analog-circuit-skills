#!/usr/bin/env python3
"""
simulate_tran_strongarm_noise.py
=================================
Noise extraction: single fixed differential input, SWEEP_NCYC cycles.
Also measures power (Vin=0) and Tcmp (Vin=+1mV).

Noise extraction method: single-point probit
    sigma_n = VIN_FIXED_V / norm.ppf(P1)

Public API
----------
simulate_noise() -> dict
    'noise_pt' : {vin_mv, count_1, p1, sigma_uv}
    'power_pt' : {vin_mv, p_avg_uw}
    'tcmp_pt'  : {vin_mv, tcmp_ps}
    'params'   : circuit/sim parameters

compute_fom(noise_results) -> dict
    {sigma_uv, p_avg_uw, tcmp_ps, fom1, fom2}
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
    sample_output, compute_tcmp, sigma_from_p1, NOISE_VIN_MV,
)

VIN_FIXED_MV = NOISE_VIN_MV   # 0.5 mV — single point for noise extraction
SWEEP_NCYC   = 1000
SWEEP_TSTOP  = SWEEP_NCYC * TCLK
SWEEP_TSTEP  = 50e-12          # 50 ps


def simulate_noise() -> dict:
    """Run 3 simulations in parallel: noise point, power point, Tcmp point."""
    print(f"\n=== Noise Extraction (single-point probit, {SWEEP_NCYC} cycles) ===")
    print(f"  Vin_fixed={VIN_FIXED_MV}mV  |  "
          f"Vin_power=0mV  |  Vin_tcmp=+1mV  |  {SWEEP_NCYC} cycles each")

    dut_include, dut_tmp = render_dut()
    tasks = [
        ("noise", lambda: _run_point(VIN_FIXED_MV, dut_include)),
        ("power", lambda: _run_point(0.0,          dut_include, measure_power=True)),
        ("tcmp",  lambda: _run_point(1.0,           dut_include, measure_tcmp=True)),
    ]

    t0 = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {name: pool.submit(fn) for name, fn in tasks}
            raw = {name: f.result() for name, f in futures.items()}
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    wall = time.perf_counter() - t0
    print(f"\n  Wall time: {wall:.1f}s (3 points in parallel)")

    return {
        "noise_pt": raw["noise"],
        "power_pt": raw["power"],
        "tcmp_pt":  raw["tcmp"],
        "params":   circuit_params({"SWEEP_NCYC": SWEEP_NCYC,
                                    "VIN_FIXED_MV": VIN_FIXED_MV}),
    }


def _run_point(vin_mv, dut_include, measure_power=False, measure_tcmp=False):
    tag      = f"noise_vin{vin_mv:+.2f}mv"
    print(f"  [{tag}] starting ...", flush=True)
    t0       = time.perf_counter()

    vin  = vin_mv * 1e-3
    log  = LOG_DIR / f"strongarm_{tag}.log"
    out  = LOG_DIR / f"strongarm_{tag}_outp.txt"

    ivdd_path = None
    ivdd_cmd  = ""
    if measure_power:
        ivdd_path = LOG_DIR / "strongarm_noise_vin0_ivdd.txt"
        ivdd_cmd  = f"wrdata {spath(ivdd_path)} i(vvdd)"

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
    count_1 = 0
    time_arr = outp_arr = None
    if raw is not None and len(raw) > 100:
        time_arr = raw[:, 0]
        outp_arr = raw[:, 1]
        count_1  = int(np.sum(sample_output(time_arr, outp_arr, SWEEP_NCYC)))
    else:
        print(f"  [{tag}] WARNING: no usable data")

    p1       = count_1 / SWEEP_NCYC
    sigma_v  = sigma_from_p1(p1, abs(vin)) if vin_mv == VIN_FIXED_MV else float("nan")
    sigma_uv = abs(sigma_v) * 1e6 if not np.isnan(sigma_v) else float("nan")

    p_avg_uw = float("nan")
    if measure_power and ivdd_path and ivdd_path.exists():
        ivdd_raw = parse_wrdata(ivdd_path)
        if ivdd_raw is not None and len(ivdd_raw) > 100:
            p_avg_uw = VDD * np.mean(np.abs(ivdd_raw[:, 1])) * 1e6

    tcmp_ps = float("nan")
    if measure_tcmp and time_arr is not None:
        tcmp_ps = compute_tcmp(time_arr, outp_arr, SWEEP_NCYC)
        print(f"  [{tag}] Tcmp = {tcmp_ps:.1f} ps", flush=True)

    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s | "
          f"Vin={vin_mv:+.2f}mV  P(1)={p1*100:.1f}%  "
          f"sigma={sigma_uv:.0f}µV", flush=True)

    return {
        "vin_mv": vin_mv, "count_1": count_1, "p1": p1,
        "sigma_uv": sigma_uv,
        "p_avg_uw": p_avg_uw, "tcmp_ps": tcmp_ps,
        "rc": rc, "elapsed": elapsed,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FOM calculation
# ─────────────────────────────────────────────────────────────────────────────
def compute_fom(noise_results) -> dict:
    """Compute FOM from noise results (single-point probit method)."""
    noise_pt = noise_results["noise_pt"]
    power_pt = noise_results["power_pt"]
    tcmp_pt  = noise_results["tcmp_pt"]
    params   = noise_results["params"]

    sigma_uv = noise_pt["sigma_uv"]
    p_avg_uw = power_pt["p_avg_uw"]
    tcmp_ps  = tcmp_pt["tcmp_ps"]

    FCLK_GHZ = FCLK / 1e9
    fom1 = fom2 = float("nan")
    if not any(np.isnan([sigma_uv, p_avg_uw])):
        e_cycle_nj = p_avg_uw / FCLK_GHZ * 1e-6
        fom1 = e_cycle_nj * (sigma_uv ** 2)
    if not any(np.isnan([fom1, tcmp_ps])):
        fom2 = fom1 * (tcmp_ps / 1e3)

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
        f.write("Noise extraction (single-point probit)\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Vin_fixed    : {p['VIN_FIXED_MV']} mV\n")
        f.write(f"  Cycles       : {p['SWEEP_NCYC']}\n")
        f.write(f"  P(1)         : {noise_pt['p1']*100:.1f}%\n")
        f.write(f"  sigma_n      : {sigma_uv:.1f} uV\n")
        f.write(f"    (= {p['VIN_FIXED_MV']}mV / norm.ppf({noise_pt['p1']:.3f}))\n")
        f.write("\n")
        f.write("Performance metrics\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Avg power    : {p_avg_uw:.2f} uW  (Vin=0, {SWEEP_NCYC} cycles)\n")
        f.write(f"  Tcmp         : {tcmp_ps:.1f} ps  (Vin=+1mV, {SWEEP_NCYC} cycles)\n")
        f.write("\n")
        f.write("Figure of Merit\n")
        f.write("-" * 40 + "\n")
        f.write(f"  FOM1 = E_cycle x sigma_n^2  : {fom1:.4g} nJ*uV^2\n")
        f.write(f"  FOM2 = FOM1 x Tcmp          : {fom2:.4g} nJ*uV^2*ns\n")
        f.write("\n")
        f.write("  Reference (45nm, 1GHz): FOM1 ~ 8-30 nJ*uV^2\n")
        f.write(f"\nReport: {log_path}\n")

    print(f"\n  FOM report -> {log_path}")
    return dict(sigma_uv=sigma_uv, p_avg_uw=p_avg_uw, tcmp_ps=tcmp_ps,
                fom1=fom1, fom2=fom2)
