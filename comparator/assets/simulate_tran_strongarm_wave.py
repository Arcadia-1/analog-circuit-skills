#!/usr/bin/env python3
"""
simulate_tran_strongarm_wave.py
================================
Waveform simulation: 3 cycles, Vin=+1mV, all internal nodes.
Testbench: testbench_cmp_tran.cir.tmpl (clean DC input, no trnoise).

Public API
----------
simulate_wave() -> dict
    'wave'   : {time, clk, inp, inn, vxp, vxn, vlp, vln, outp, outn}
    'params' : circuit/sim parameters
"""

import os
import time
import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from comparator_common import (
    VDD, VCM, TCLK,
    circuit_params, render_dut, common_kw, run_netlist,
    compute_tau_from_latch,
)

WAVE_VIN_MV = 1.0          # mV  overdrive for waveform
WAVE_NCYC   = 3            # number of clock cycles to simulate
WAVE_TSTOP  = WAVE_NCYC * TCLK
WAVE_TSTEP  = 2e-12        # 2 ps  (5 pts per 10 ps clock edge → smooth waveform)


def simulate_wave() -> dict:
    """Run 3-cycle waveform simulation at Vin=+1mV."""
    print("\n=== Waveform Simulation (3 cycles, Vin=+1mV) ===")
    dut_include, dut_tmp = render_dut()
    try:
        wave = _run_wave(WAVE_VIN_MV, dut_include)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    return {
        "wave":   wave,
        "params": circuit_params({"WAVE_NCYC": WAVE_NCYC, "WAVE_VIN_MV": WAVE_VIN_MV}),
    }


def _run_wave(vin_mv, dut_include):
    tag = f"wave_vin{vin_mv:+.0f}mv"
    print(f"  [{tag}] starting ...", flush=True)
    t0  = time.perf_counter()

    vin   = vin_mv * 1e-3
    log   = LOG_DIR / f"strongarm_{tag}.log"
    paths = {sig: LOG_DIR / f"strongarm_{tag}_{sig}.txt"
             for sig in ("clk", "inp", "inn", "vxp", "vxn", "vlp", "vln", "outp", "outn")}

    kw = dict(
        **common_kw(dut_include),
        vin_label = vin_mv,
        vinp_dc   = VCM + vin / 2,
        vinn_dc   = VCM - vin / 2,
        tstep     = f"{WAVE_TSTEP:.4e}",
        tstop     = f"{WAVE_TSTOP:.4e}",
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_cmp_tran.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        p = paths[key]
        d = parse_wrdata(p) if p.exists() else None
        return (d[:, 0], d[:, 1]) if d is not None else (None, None)

    t,   clk  = _load("clk")
    _,   inp  = _load("inp")
    _,   inn  = _load("inn")
    _,   vxp  = _load("vxp")
    _,   vxn  = _load("vxn")
    _,   vlp  = _load("vlp")
    _,   vln  = _load("vln")
    _,   outp = _load("outp")
    _,   outn = _load("outn")

    tau_ps = float("nan")
    if t is not None and vlp is not None and vln is not None:
        tau_ps = compute_tau_from_latch(t, vlp, vln, WAVE_NCYC)
        if not np.isnan(tau_ps):
            print(f"  [{tag}] τ = {tau_ps:.1f} ps", flush=True)

    return {
        "vin_mv": vin_mv, "rc": rc, "elapsed": elapsed,
        "time": t, "clk": clk, "inp": inp, "inn": inn,
        "vxp": vxp, "vxn": vxn, "vlp": vlp, "vln": vln,
        "outp": outp, "outn": outn,
        "tau_ps": tau_ps,
    }
