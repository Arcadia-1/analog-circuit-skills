#!/usr/bin/env python3
"""
simulate_sweep_input_amplitude.py
==================================
StrongArm: sweep input differential amplitude Vin_diff → decision time Tcmp.

Sweep: Vin_diff = 1e-9 V … 1e-1 V, N_AMPL points (log-spaced), no noise.
For each Vin_diff: run a 1-cycle transient and measure CLK→OUTP crossing time.
If OUTP never crosses VDD/2 within the clock cycle, Tcmp = NaN (metastable).

Public API
----------
sweep_input_amplitude() -> list of dicts
    Each dict: {vin_v, vin_mv, tcmp_ps, resolved}
"""

import os
import sys
import time
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import LOG_DIR, MODEL_DIR, parse_wrdata, spath
from comparator_common import VDD, VCM, TCLK, W, L_NM, render_dut, common_kw, run_netlist

N_AMPL      = 100
VIN_START   = 1e-12   # V
VIN_STOP    = 1e-1    # V
VIN_VALS    = np.logspace(np.log10(VIN_START), np.log10(VIN_STOP), N_AMPL)  # V

# 1 cycle sim, fine step for accurate crossing detection
TSTOP  = TCLK
TSTEP  = 2e-12    # 2 ps

# Max workers — 100 parallel sims; limit to avoid memory pressure
MAX_WORKERS = 20


def _run_one(vin_v, dut_include):
    tag = f"ampl_{vin_v:.3e}v".replace("+", "").replace("-", "m")
    log  = LOG_DIR / f"sweep_ampl_{tag}.log"
    out  = LOG_DIR / f"sweep_ampl_{tag}_outp.txt"

    kw = dict(
        **common_kw(dut_include),
        vin_label = vin_v * 1e3,
        vinp_dc   = VCM + vin_v / 2,
        vinn_dc   = VCM - vin_v / 2,
        tstep     = f"{TSTEP:.4e}",
        tstop     = f"{TSTOP:.4e}",
        out_clk   = spath(LOG_DIR / f"sweep_ampl_{tag}_clk.txt"),
        out_inp   = spath(LOG_DIR / f"sweep_ampl_{tag}_inp.txt"),
        out_inn   = spath(LOG_DIR / f"sweep_ampl_{tag}_inn.txt"),
        out_vxp   = spath(LOG_DIR / f"sweep_ampl_{tag}_vxp.txt"),
        out_vxn   = spath(LOG_DIR / f"sweep_ampl_{tag}_vxn.txt"),
        out_vlp   = spath(LOG_DIR / f"sweep_ampl_{tag}_vlp.txt"),
        out_vln   = spath(LOG_DIR / f"sweep_ampl_{tag}_vln.txt"),
        out_outp  = spath(out),
        out_outn  = spath(LOG_DIR / f"sweep_ampl_{tag}_outn.txt"),
        out_ivdd  = spath(LOG_DIR / f"sweep_ampl_{tag}_ivdd.txt"),
    )
    run_netlist("testbench_cmp_tran.cir.tmpl", kw, log)

    raw = parse_wrdata(out) if out.exists() else None
    tcmp_ps = float("nan")
    resolved = False

    if raw is not None and len(raw) > 10:
        t_arr    = raw[:, 0]
        outp_arr = raw[:, 1]
        half     = VDD / 2
        clk_rise = 5e-12   # CLK crosses VDD/2 at TR/2 = 5ps after t=0

        for i in range(len(outp_arr) - 1):
            if t_arr[i] < clk_rise:
                continue
            if outp_arr[i] < half <= outp_arr[i + 1]:
                frac = (half - outp_arr[i]) / (outp_arr[i + 1] - outp_arr[i])
                t_cross = t_arr[i] + frac * (t_arr[i + 1] - t_arr[i])
                tcmp_ps = (t_cross - clk_rise) * 1e12
                resolved = True
                break

    return {"vin_v": vin_v, "vin_mv": vin_v * 1e3, "tcmp_ps": tcmp_ps, "resolved": resolved}


def sweep_input_amplitude() -> list:
    """Sweep Vin_diff over log-spaced range, measure Tcmp for each point."""
    print(f"\n=== StrongArm: Input Amplitude Sweep  ({N_AMPL} points, 1 cycle each) ===")
    print(f"  Vin range: {VIN_START:.0e} – {VIN_STOP:.0e} V  (log-spaced, no noise)")

    dut_include, dut_tmp = render_dut()
    t_total = time.perf_counter()
    results = []
    try:
        # Process in batches to limit simultaneous file handles
        for batch_start in range(0, N_AMPL, MAX_WORKERS):
            batch = VIN_VALS[batch_start: batch_start + MAX_WORKERS]
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                futs = [pool.submit(_run_one, v, dut_include) for v in batch]
                for f in futs:
                    results.append(f.result())
            n_done = min(batch_start + MAX_WORKERS, N_AMPL)
            print(f"  {n_done}/{N_AMPL} points done ...", flush=True)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    results.sort(key=lambda r: r["vin_v"])
    n_resolved = sum(1 for r in results if r["resolved"])
    print(f"\n  Total wall time: {time.perf_counter() - t_total:.1f}s  "
          f"({n_resolved}/{N_AMPL} resolved within 1 cycle)")
    return results
