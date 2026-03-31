#!/usr/bin/env python3
"""
simulate_ldo_tran.py
====================
Transient simulation: VOUT load-step response.

Public API
----------
simulate_tran() -> dict
    'tran'    : {time, vout, vin}
    'metrics' : {vout_ss_mv, v_drop_mv, load_reg_tran_mv,
                 v_overshoot_mv, t_rec_us}
    'params'  : circuit/sim parameters
"""

import time
import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ldo_common import (
    VIN_NOM, VREF_NOM, MODEL_PATH,
    circuit_params, render_dut, run_netlist,
)

# ── Transient parameters ─────────────────────────────────────────────────────
R_IDLE     = 1800.0   # Ω   idle light load  (~1 mA at 1.8 V)
ILOAD_STEP = 0.1      # A   load-current step (100 mA)
T_PRE      = 10e-6    # s   pre-step window (DC OP gives correct initial state)
TRISE      = 100e-9   # s   current step rise time
TFALL      = 100e-9   # s   current step fall time
T_STEP_ON  = 50e-6    # s   load step duration
TSTOP      = 100e-6   # s   total sim time (10 µs idle + 50 µs load + 40 µs recovery)
TSTEP      = 5e-9     # s   time step


def simulate_tran() -> dict:
    """Run load-step transient simulation."""
    print("\n=== LDO Transient Simulation (Load Step) ===")
    dut_include, _ = render_dut()
    return _run_tran(dut_include)


def _run_tran(dut_include):
    tag = "ldo_tran"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log = LOG_DIR / f"{tag}.log"
    paths = {
        "vout": LOG_DIR / f"{tag}_vout.txt",
        "vin":  LOG_DIR / f"{tag}_vin.txt",
    }

    kw = dict(
        vin_dc      = VIN_NOM,
        vref_dc     = VREF_NOM,
        r_idle      = R_IDLE,
        iload_step  = f"{ILOAD_STEP:.6g}",
        t_pre       = f"{T_PRE:.6e}",
        trise       = f"{TRISE:.6e}",
        tfall       = f"{TFALL:.6e}",
        t_step_on   = f"{T_STEP_ON:.6e}",
        t_period    = f"{TSTOP * 2:.6e}",   # single pulse: period >> tstop
        tstep       = f"{TSTEP:.6e}",
        tstop       = f"{TSTOP:.6e}",
        dut_include = dut_include,
        model_path  = MODEL_PATH,
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_ldo_tran.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        d = parse_wrdata(paths[key])
        return (d[:, 0], d[:, 1]) if d is not None else (None, None)

    t,   vout = _load("vout")
    _,   vin  = _load("vin")

    metrics = _extract_metrics(t, vout)
    return {
        "tran":    {"time": t, "vout": vout, "vin": vin},
        "metrics": metrics,
        "rc":      rc,
        "elapsed": elapsed,
        "params":  circuit_params({
            "R_IDLE":     R_IDLE,
            "ILOAD_STEP": ILOAD_STEP,
            "T_PRE":      T_PRE,
            "TRISE":      TRISE,
            "T_STEP_ON":  T_STEP_ON,
            "TSTOP":      TSTOP,
        }),
    }


def _extract_metrics(t, vout):
    metrics = {}
    if t is None or vout is None:
        return metrics

    t_step_start = T_PRE
    t_step_end   = T_PRE + T_STEP_ON

    # Pre-step steady state: last 60% of pre-step window
    mask_pre = (t > T_PRE * 0.4) & (t < t_step_start)
    if mask_pre.sum() == 0:
        return metrics
    vout_ss = float(np.mean(vout[mask_pre]))
    metrics["vout_ss_mv"] = vout_ss * 1e3
    print(f"  [tran] VOUT_SS (light load) = {vout_ss * 1e3:.3f} mV", flush=True)

    # Undershoot: minimum VOUT during step
    mask_step = (t >= t_step_start) & (t <= t_step_end)
    if mask_step.sum() > 0:
        vout_min = float(np.min(vout[mask_step]))
        metrics["vout_min_mv"] = vout_min * 1e3
        metrics["v_drop_mv"]   = (vout_ss - vout_min) * 1e3
        print(f"  [tran] VOUT_min = {vout_min*1e3:.3f} mV  "
              f"V_drop = {metrics['v_drop_mv']:.2f} mV", flush=True)

        # Heavy-load steady state: average of last 20% of step-on window
        t_heavy_start = t_step_start + T_STEP_ON * 0.7
        t_heavy_end   = t_step_end - TRISE * 5
        mask_heavy = (t >= t_heavy_start) & (t <= t_heavy_end)
        if mask_heavy.sum() > 0:
            vout_heavy = float(np.mean(vout[mask_heavy]))
            metrics["vout_heavy_mv"]    = vout_heavy * 1e3
            metrics["load_reg_tran_mv"] = (vout_ss - vout_heavy) * 1e3
            print(f"  [tran] VOUT_heavy = {vout_heavy*1e3:.3f} mV  "
                  f"ΔVout(DC) = {metrics['load_reg_tran_mv']:.2f} mV", flush=True)

    # Overshoot: max VOUT in early post-step window (within 30% of step duration)
    mask_post_early = (t >= t_step_end) & (t <= t_step_end + T_STEP_ON * 0.3)
    if mask_post_early.sum() > 0:
        vout_max    = float(np.max(vout[mask_post_early]))
        v_overshoot = vout_max - vout_ss
        if v_overshoot > 1e-4:   # > 0.1 mV threshold
            metrics["v_overshoot_mv"] = v_overshoot * 1e3
            print(f"  [tran] V_overshoot = {v_overshoot*1e3:.2f} mV", flush=True)

    # Recovery time: from step-end until VOUT stays within 1% of vout_ss
    tolerance  = abs(vout_ss) * 0.01
    mask_rec   = t >= t_step_end
    if mask_rec.sum() > 1:
        t_rec  = t[mask_rec]
        v_rec  = vout[mask_rec]
        still_off = np.abs(v_rec - vout_ss) > tolerance
        idx = np.where(still_off)[0]
        if len(idx) > 0:
            last = idx[-1]
            if last + 1 < len(t_rec):
                t_recovery = float(t_rec[last + 1] - t_step_end)
                metrics["t_rec_us"] = t_recovery * 1e6
                print(f"  [tran] Recovery time (1%) = {t_recovery*1e6:.2f} us",
                      flush=True)

    return metrics
