#!/usr/bin/env python3
"""
simulate_tran_strongarm_ramp.py
================================
Ramp simulation: Vin sweeps from -2mV to +2mV over 100 cycles.
Testbench: testbench_cmp_ramp.cir.tmpl

Public API
----------
simulate_ramp() -> dict
    'ramp'   : {time, vout_diff, vin_diff}
    'params' : circuit/sim parameters
"""

import os
import time
import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from comparator_common import (
    VCM, TCLK,
    circuit_params, render_dut, common_kw, run_netlist,
)

RAMP_NCYC      = 100
RAMP_TSTOP     = RAMP_NCYC * TCLK
RAMP_TSTEP     = 50e-12
RAMP_VIN_START = -2e-3   # V
RAMP_VIN_END   = +2e-3   # V


def simulate_ramp() -> dict:
    """Run 100-cycle ramp simulation."""
    print("\n=== Ramp Simulation (100 cycles, -2mV → +2mV) ===")
    dut_include, dut_tmp = render_dut()
    try:
        ramp = _run_ramp(dut_include)
    finally:
        os.unlink(dut_tmp)

    return {
        "ramp":   ramp,
        "params": circuit_params({"RAMP_NCYC": RAMP_NCYC}),
    }


def _run_ramp(dut_include):
    tag = "ramp"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log      = LOG_DIR / "strongarm_ramp.log"
    out_outp = LOG_DIR / "strongarm_ramp_outp.txt"
    out_outn = LOG_DIR / "strongarm_ramp_outn.txt"
    out_inp  = LOG_DIR / "strongarm_ramp_inp.txt"
    out_inn  = LOG_DIR / "strongarm_ramp_inn.txt"

    vinp_start = VCM + RAMP_VIN_START / 2
    vinp_end   = VCM + RAMP_VIN_END   / 2
    vinn_start = VCM - RAMP_VIN_START / 2
    vinn_end   = VCM - RAMP_VIN_END   / 2

    kw = dict(
        **common_kw(dut_include),
        vin_start_mv = RAMP_VIN_START * 1e3,
        vin_end_mv   = RAMP_VIN_END   * 1e3,
        n_cycles     = RAMP_NCYC,
        vinp_start   = f"{vinp_start:.10f}",
        vinp_end     = f"{vinp_end:.10f}",
        vinn_start   = f"{vinn_start:.10f}",
        vinn_end     = f"{vinn_end:.10f}",
        tstep        = f"{RAMP_TSTEP:.4e}",
        tstop        = f"{RAMP_TSTOP:.4e}",
        out_outp     = spath(out_outp),
        out_outn     = spath(out_outn),
        out_inp      = spath(out_inp),
        out_inn      = spath(out_inn),
    )
    rc = run_netlist("testbench_cmp_ramp.cir.tmpl", kw, LOG_DIR / "strongarm_ramp.log")
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(p):
        d = parse_wrdata(p) if p.exists() else None
        return (d[:, 0], d[:, 1]) if d is not None and len(d) > 10 else (None, None)

    time_arr, outp_arr = _load(out_outp)
    _,        outn_arr = _load(out_outn)
    _,        inp_arr  = _load(out_inp)
    _,        inn_arr  = _load(out_inn)

    vout_diff = (outp_arr - outn_arr) if (outp_arr is not None and outn_arr is not None) else None
    vin_diff  = ((inp_arr - inn_arr) * 1e3) if (inp_arr is not None and inn_arr is not None) else None

    return {
        "rc": rc, "elapsed": elapsed,
        "time": time_arr,
        "vout_diff": vout_diff,   # OUTP - OUTN [V]
        "vin_diff":  vin_diff,    # INP  - INN  [mV]
    }
