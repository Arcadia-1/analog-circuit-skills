#!/usr/bin/env python3
"""
simulate_ldo_dc.py
==================
DC simulations: operating point, line regulation, load regulation.

Public API
----------
simulate_dc() -> dict
    'op'         : {vout, vin, vref}  operating-point voltages
    'line_reg'   : {vin_arr, vout_arr}  line regulation sweep
    'load_reg'   : {iload_arr, vout_arr}  load regulation sweep
    'params'     : circuit/sim parameters
"""

import time
import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ldo_common import (
    VIN_NOM, VOUT_NOM, VREF_NOM, MODEL_PATH, R_LOAD_DEFAULT,
    circuit_params, render_dut, run_netlist,
)

# ── DC sweep parameters ───────────────────────────────────────────────────────
VIN_MIN     = 1.6    # V  line-reg sweep start (含dropout区，用于完整图形)
VIN_REG_MIN = 2.0    # V  计算线性调整率指标的起点
VIN_MAX   = 3.3    # V  line-reg sweep end
VIN_STEP  = 0.05   # V  line-reg step

ILOAD_MAX  = 0.1   # A   load-reg sweep max (100 mA)
ILOAD_STEP = 0.001 # A   1 mA step


def simulate_dc() -> dict:
    """Run DC operating point, line regulation, and load regulation."""
    print("\n=== LDO DC Simulations ===")
    dut_include, _ = render_dut()
    return _run_dc(dut_include)


def _run_dc(dut_include):
    tag = "ldo_dc"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log = LOG_DIR / f"{tag}.log"
    paths = {
        "line_vin":    LOG_DIR / f"{tag}_line_vin.txt",
        "line_vout":   LOG_DIR / f"{tag}_line_vout.txt",
        "load_iload":  LOG_DIR / f"{tag}_load_iload.txt",
        "load_vout":   LOG_DIR / f"{tag}_load_vout.txt",
    }

    kw = dict(
        vin_dc    = VIN_NOM,
        vref_dc   = VREF_NOM,
        r_load    = R_LOAD_DEFAULT,
        vin_min   = VIN_MIN,
        vin_max   = VIN_MAX,
        vin_step  = VIN_STEP,
        iload_max  = ILOAD_MAX,
        iload_step = ILOAD_STEP,
        dut_include = dut_include,
        model_path  = MODEL_PATH,
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_ldo_dc.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        p = paths[key]
        d = parse_wrdata(p) if p.exists() else None
        return d[:, 1] if d is not None else None

    line_vin   = _load("line_vin")
    line_vout  = _load("line_vout")
    load_iload = _load("load_iload")
    load_vout  = _load("load_vout")

    # Operating-point values extracted from nominal point of line-reg sweep
    op_vout = float("nan")
    op_vin  = VIN_NOM
    if line_vin is not None and line_vout is not None:
        idx = np.argmin(np.abs(line_vin - VIN_NOM))
        op_vout = float(line_vout[idx])
        print(f"  [op] Vout @ Vin={VIN_NOM}V: {op_vout*1e3:.2f} mV", flush=True)

    # Line regulation metric: ΔVout / ΔVin  (mV/V)
    # 只在调节区（VIN >= VIN_REG_MIN）计算，排除 dropout 区的影响
    if line_vin is not None and line_vout is not None and len(line_vin) > 1:
        mask = line_vin >= VIN_REG_MIN
        if mask.sum() > 1:
            delta_v = float(line_vout[mask][-1] - line_vout[mask][0])
            delta_vin = float(line_vin[mask][-1] - line_vin[mask][0])
        else:
            delta_v = float(line_vout[-1] - line_vout[0])
            delta_vin = float(line_vin[-1] - line_vin[0])
        linereg_mv_per_v = delta_v / delta_vin * 1e3
        print(f"  [line_reg] ΔVout/ΔVin = {linereg_mv_per_v:.2f} mV/V (VIN≥{VIN_REG_MIN}V)", flush=True)

    # Load regulation metric: ΔVout at Iload=Imax vs Iload=0  (mV)
    if load_vout is not None and len(load_vout) > 1:
        delta_vout_load = float(load_vout[-1] - load_vout[0])
        print(f"  [load_reg] ΔVout (0→{ILOAD_MAX*1e3:.0f}mA) = {delta_vout_load*1e3:.2f} mV",
              flush=True)

    return {
        "op": {"vout": op_vout, "vin": op_vin, "vref": VREF_NOM},
        "line_reg": {"vin_arr": line_vin, "vout_arr": line_vout},
        "load_reg": {"iload_arr": load_iload, "vout_arr": load_vout},
        "rc": rc,
        "elapsed": elapsed,
        "params": circuit_params({
            "VIN_MIN": VIN_MIN, "VIN_MAX": VIN_MAX,
            "ILOAD_MAX": ILOAD_MAX, "R_LOAD": R_LOAD_DEFAULT,
        }),
    }
