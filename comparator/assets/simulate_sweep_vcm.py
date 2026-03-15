#!/usr/bin/env python3
"""
simulate_sweep_vcm.py
=====================
StrongArm: sweep VCM → input-referred noise sigma_n.

Noise extraction method: single fixed differential input (single-point probit).
  For each VCM, run SWEEP_NCYC cycles at Vdiff = VIN_FIXED_MV.
  Count P(1), then:
      sigma_n = VIN_FIXED_V / norm.ppf(P1)

This is 9× faster than the 9-point CDF sweep approach.

Public API
----------
sweep_vcm(ncyc=None) -> list of dicts
    Each dict: {vcm, p1, sigma_uv, wall_s}
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
    sample_output, sigma_from_p1, NOISE_VIN_MV,
)

N_VCM          = 20
VCM_START      = 0.50 * VDD
VCM_STOP       = 0.75 * VDD
VCM_VALS       = list(np.linspace(VCM_START, VCM_STOP, N_VCM))

VIN_FIXED_MV   = NOISE_VIN_MV   # 0.5 mV fixed differential input
SWEEP_NCYC     = 200             # cycles per VCM point
SWEEP_TSTEP    = 500e-12         # 500 ps output step
SWEEP_NOISE_NT = 50e-12          # 50 ps → BW = 10 GHz (10× clock)
MAX_WORKERS    = N_VCM


def _run_one_vcm(vcm, dut_include, ncyc):
    """Run one ngspice process at VIN_FIXED_MV for a given VCM, count P(1)."""
    tag = f"sweep_vcm_vcm{vcm*1000:.0f}mv"
    log = LOG_DIR / f"{tag}.log"
    out = LOG_DIR / f"{tag}_outp.txt"

    vin  = VIN_FIXED_MV * 1e-3
    vinp = vcm + vin / 2
    vinn = vcm - vin / 2

    base_kw = common_kw(dut_include)
    base_kw["noise_nt"]    = f"{SWEEP_NOISE_NT:.4e}"
    base_kw["noise_nt_ps"] = SWEEP_NOISE_NT * 1e12

    kw = dict(
        **base_kw,
        vin_label = VIN_FIXED_MV,
        inp_src   = f"VINP_DC INP_DC 0 DC {vinp:.10f}",
        inn_src   = f"VINN_DC INN_DC 0 DC {vinn:.10f}",
        tstep     = f"{SWEEP_TSTEP:.4e}",
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

    return {"vcm": vcm, "p1": p1, "sigma_uv": sigma_uv, "wall_s": 0.0}


def sweep_vcm(ncyc=None) -> list:
    """Run N_VCM ngspice calls in parallel, each at fixed VIN_FIXED_MV."""
    if ncyc is None:
        ncyc = SWEEP_NCYC

    print(f"\n=== StrongArm: VCM Sweep  "
          f"({N_VCM} VCM points, {ncyc} cycles/point, "
          f"Vin_fixed={VIN_FIXED_MV}mV, {N_VCM} parallel) ===")
    print(f"  VCM: {VCM_START:.3f}–{VCM_STOP:.3f}V  "
          f"NT={SWEEP_NOISE_NT*1e12:.0f}ps  BW={1/(2*SWEEP_NOISE_NT)/1e9:.0f}GHz\n")

    dut_include, dut_tmp = render_dut()

    t_start = time.perf_counter()
    raw_results = {}
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {
                pool.submit(_run_one_vcm, vcm, dut_include, ncyc): vcm
                for vcm in VCM_VALS
            }
            for f in as_completed(future_map):
                vcm_f = future_map[f]
                try:
                    raw_results[vcm_f] = f.result()
                except Exception as exc:
                    print(f"  WARN: VCM={vcm_f:.3f}V failed: {exc}", flush=True)
                    raw_results[vcm_f] = {
                        "vcm": vcm_f, "p1": float("nan"),
                        "sigma_uv": float("nan"), "wall_s": 0.0,
                    }
                r = raw_results[vcm_f]
                print(f"  VCM={vcm_f:.3f}V  P(1)={r['p1']*100:.1f}%  "
                      f"sigma={r['sigma_uv']:.0f}µV  "
                      f"({time.perf_counter()-t_start:.1f}s)", flush=True)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    wall = time.perf_counter() - t_start
    print(f"\n  Total wall time: {wall:.1f}s")

    results = []
    for vcm in VCM_VALS:
        r = raw_results[vcm]
        r["wall_s"] = wall
        results.append(r)
    return results
