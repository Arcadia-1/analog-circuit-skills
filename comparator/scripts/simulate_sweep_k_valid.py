#!/usr/bin/env python3
"""
simulate_sweep_k_valid.py
=========================
Validate the single-point probit noise method by sweeping k (fixed differential
input amplitude) at a fixed VCM and checking that sigma_n = k / norm.ppf(P1)
is consistent across all k values.

If the method is correct, sigma_n should be flat (within statistical noise).
Ideal range: P(1) in [0.65, 0.95], i.e. k in [0.5σ, 1.5σ].

Public API
----------
sweep_k(vcm=None, ncyc=None) -> list of dicts
    Each dict: {k_mv, p1, sigma_uv}
"""

import os
import sys
import time
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import LOG_DIR, parse_wrdata, spath
from comparator_common import (
    VDD, TCLK,
    render_dut, common_kw, run_netlist,
    sample_output, sigma_from_p1,
)

VCM_FIXED  = 0.60 * VDD          # fixed VCM near noise minimum
K_MV_VALS  = list(np.linspace(0.15, 1.5, 20))   # 20 k values (mV)
NCYC       = 500                  # cycles per k point
TSTEP      = 500e-12              # 500 ps
NOISE_NT   = 50e-12               # 50 ps → BW = 10 GHz
MAX_WORKERS = len(K_MV_VALS)


def _run_one_k(k_mv, dut_include, ncyc):
    """Run one simulation at fixed VCM, fixed k_mv, count P(1)."""
    tag = f"kval_k{k_mv*1000:.0f}uv"
    log = LOG_DIR / f"{tag}.log"
    out = LOG_DIR / f"{tag}_outp.txt"

    vin  = k_mv * 1e-3
    vinp = VCM_FIXED + vin / 2
    vinn = VCM_FIXED - vin / 2

    base_kw = common_kw(dut_include)
    base_kw["noise_nt"]    = f"{NOISE_NT:.4e}"
    base_kw["noise_nt_ps"] = NOISE_NT * 1e12

    kw = dict(
        **base_kw,
        vin_label = k_mv,
        inp_src   = f"VINP_DC INP_DC 0 DC {vinp:.10f}",
        inn_src   = f"VINN_DC INN_DC 0 DC {vinn:.10f}",
        tstep     = f"{TSTEP:.4e}",
        tstop     = f"{ncyc * TCLK:.4e}",
        out_outp  = spath(out),
        ivdd_cmd  = "",
    )
    run_netlist("testbench_cmp_tran_noise.cir.tmpl", kw, log)

    raw = parse_wrdata(out) if out.exists() else None
    count_1 = 0
    if raw is not None and len(raw) >= ncyc:
        count_1 = int(np.sum(sample_output(raw[:, 0], raw[:, 1], ncyc)))

    p1      = count_1 / ncyc
    sigma_v = sigma_from_p1(p1, vin)
    sigma_uv = abs(sigma_v) * 1e6 if not np.isnan(sigma_v) else float("nan")

    return {"k_mv": k_mv, "p1": p1, "sigma_uv": sigma_uv}


def sweep_k(vcm=None, ncyc=None) -> list:
    """Run all k points in parallel at fixed VCM."""
    _vcm  = vcm  if vcm  is not None else VCM_FIXED
    _ncyc = ncyc if ncyc is not None else NCYC

    print(f"\n=== k-Validation Sweep  "
          f"({len(K_MV_VALS)} k points, {_ncyc} cycles/point, "
          f"VCM={_vcm:.3f}V, {MAX_WORKERS} parallel) ===")
    print(f"  k: {K_MV_VALS[0]:.2f}–{K_MV_VALS[-1]:.2f}mV  "
          f"NT={NOISE_NT*1e12:.0f}ps  BW={1/(2*NOISE_NT)/1e9:.0f}GHz\n")

    dut_include, dut_tmp = render_dut()

    t_start = time.perf_counter()
    raw_results = {}
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {
                pool.submit(_run_one_k, k_mv, dut_include, _ncyc): k_mv
                for k_mv in K_MV_VALS
            }
            for f in as_completed(future_map):
                k_f = future_map[f]
                try:
                    raw_results[k_f] = f.result()
                except Exception as exc:
                    print(f"  WARN: k={k_f:.3f}mV failed: {exc}", flush=True)
                    raw_results[k_f] = {"k_mv": k_f, "p1": float("nan"),
                                        "sigma_uv": float("nan")}
                r = raw_results[k_f]
                print(f"  k={k_f:.3f}mV  P(1)={r['p1']*100:.1f}%  "
                      f"sigma={r['sigma_uv']:.0f}µV  "
                      f"({time.perf_counter()-t_start:.1f}s)", flush=True)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    wall = time.perf_counter() - t_start
    print(f"\n  Total wall time: {wall:.1f}s")

    results = [raw_results[k] for k in K_MV_VALS]
    for r in results:
        r["wall_s"] = wall
    return results
