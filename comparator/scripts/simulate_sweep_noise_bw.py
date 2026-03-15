#!/usr/bin/env python3
"""
simulate_sweep_noise_bw.py
==========================
StrongArm: sweep trnoise bandwidth → input-referred noise sigma_n.

The trnoise source update interval NT = 1/(2*BW) controls both:
  - The noise correlation time (shorter NT = wider band, more decorrelated)
  - The ngspice forced max timestep (shorter NT = more simulation steps = slower)

Sweep: BW = 1 GHz … 50 GHz (NT = 500ps … 10ps), N_BW log-spaced points.
One ngspice call per BW — each runs all Vin values sequentially in .control.

Public API
----------
sweep_noise_bw() -> list of dicts
    Each dict: {bw_ghz, nt_ps, sigma_uv, mu_uv, fit_ok, vin_arr, p1_arr, p1_fit}
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
    VDD, VCM, TCLK,
    render_dut, common_kw, run_netlist,
    sample_output, fit_transfer_curve,
    NOISE_NA,
)

# ── Sweep parameters ──────────────────────────────────────────────────────────
N_BW        = 8
BW_START    = 1e9    # 1 GHz
BW_STOP     = 50e9   # 50 GHz
BW_VALS     = list(np.geomspace(BW_START, BW_STOP, N_BW))  # Hz
NT_VALS     = [1 / (2 * bw) for bw in BW_VALS]             # s  (500ps … 10ps)

VIN_MV_VALS = list(np.linspace(-1.5, 1.5, 7))  # 7 Vin points — adequate CDF fit

# Adaptive cycle count: keep forced-step count ≈ constant across BW values.
# forced_steps_per_sim = NCYC × TCLK / NT
# Target ≈ 60 forced steps → NCYC = 60 × NT / TCLK (min 8 for statistics).
_TARGET_STEPS = 200   # 100 cycles at NT=500ps (BW=1GHz); scales down for higher BW
NCYC_VALS = [max(8, int(round(_TARGET_STEPS * nt / TCLK))) for nt in NT_VALS]

SWEEP_TSTEP = 500e-12   # 500ps output step (coarse; we only need per-cycle samples)
MAX_WORKERS = N_BW      # all BW values run in parallel


def _build_sweep_cmds_bw(nt_s, ncyc, out_prefix):
    """Generate .control body: alter Vin, tran, wrdata, reset for each Vin point."""
    tstop = f"{ncyc * TCLK:.6e}"
    tstep = f"{SWEEP_TSTEP:.4e}"
    lines = []
    for vin_mv in VIN_MV_VALS:
        vin  = vin_mv * 1e-3
        vinp = VCM + vin / 2
        vinn = VCM - vin / 2
        tag  = f"vin{vin_mv:+.4f}mv"
        out  = LOG_DIR / f"{out_prefix}_{tag}_outp.txt"
        lines += [
            f"alter VINP_DC dc = {vinp:.10f}",
            f"alter VINN_DC dc = {vinn:.10f}",
            f"tran {tstep} {tstop} uic",
            f"wrdata {spath(out)} v(outp)",
            "reset",
            "",
        ]
    return "\n".join(lines)


def _run_one_bw(bw_hz, nt_s, ncyc, dut_include):
    """Run one ngspice call for a given noise BW, sweeping all Vin values."""
    bw_ghz     = bw_hz / 1e9
    nt_ps      = nt_s * 1e12
    tag_prefix = f"sweep_nbw_bw{bw_ghz:.1f}ghz"
    log        = LOG_DIR / f"{tag_prefix}.log"

    base_kw = common_kw(dut_include)
    base_kw["noise_nt"]    = f"{nt_s:.4e}"
    base_kw["noise_nt_ps"] = nt_ps

    sweep_cmds = _build_sweep_cmds_bw(nt_s, ncyc, tag_prefix)
    kw = dict(
        **base_kw,
        vcm        = VCM,
        n_vin      = len(VIN_MV_VALS),
        sweep_cmds = sweep_cmds,
    )
    run_netlist("testbench_cmp_tran_noise_batch.cir.tmpl", kw, log)

    # Collect per-Vin results
    pts = []
    for vin_mv in VIN_MV_VALS:
        tag = f"vin{vin_mv:+.4f}mv"
        out = LOG_DIR / f"{tag_prefix}_{tag}_outp.txt"
        raw = parse_wrdata(out) if out.exists() else None
        count_1 = 0
        if raw is not None and len(raw) >= ncyc:
            count_1 = int(np.sum(sample_output(raw[:, 0], raw[:, 1], ncyc)))
        pts.append({"vin_mv": vin_mv, "p1": count_1 / ncyc})

    fit = fit_transfer_curve(pts)
    return dict(
        bw_ghz   = bw_ghz,
        nt_ps    = nt_ps,
        ncyc     = ncyc,
        **{k: fit[k] for k in ("sigma_uv", "mu_uv", "fit_ok",
                                "vin_arr", "p1_arr", "p1_fit")},
    )


def sweep_noise_bw() -> list:
    """Run N_BW ngspice calls in parallel, one per noise BW value."""
    print(f"\n=== StrongArm: Noise BW Sweep  ({N_BW} BW points) ===")
    print(f"  BW: {BW_START/1e9:.0f}–{BW_STOP/1e9:.0f} GHz  "
          f"(NT: {NT_VALS[0]*1e12:.0f}–{NT_VALS[-1]*1e12:.0f} ps)")
    print(f"  Vin: {VIN_MV_VALS[0]:.2f}–{VIN_MV_VALS[-1]:.2f}mV  "
          f"({len(VIN_MV_VALS)} points)  |  "
          f"adaptive cycles: {NCYC_VALS[0]}…{NCYC_VALS[-1]}\n")

    dut_include, dut_tmp = render_dut()

    t_start = time.perf_counter()
    results = []
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {
                pool.submit(_run_one_bw, bw, nt, ncyc, dut_include): (bw, nt, ncyc)
                for bw, nt, ncyc in zip(BW_VALS, NT_VALS, NCYC_VALS)
            }
            for f in as_completed(future_map):
                bw_f, nt_f, ncyc_f = future_map[f]
                try:
                    r = f.result()
                    results.append(r)
                    print(f"  BW={r['bw_ghz']:.1f}GHz  NT={r['nt_ps']:.0f}ps  "
                          f"ncyc={ncyc_f}  "
                          f"sigma={r['sigma_uv']:.0f}µV  "
                          f"fit_ok={r['fit_ok']}  "
                          f"({time.perf_counter()-t_start:.1f}s)",
                          flush=True)
                except Exception as exc:
                    print(f"  WARN: BW={bw_f/1e9:.1f}GHz failed: {exc}", flush=True)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    wall = time.perf_counter() - t_start
    print(f"\n  Total wall time: {wall:.1f}s")

    results.sort(key=lambda r: r["bw_ghz"])
    for r in results:
        r["wall_s"] = wall
    return results
