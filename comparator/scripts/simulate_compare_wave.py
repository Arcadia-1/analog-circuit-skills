#!/usr/bin/env python3
"""
simulate_compare_wave.py
========================
Run StrongArm and Miyahara waveform simulations in parallel (3 cycles).
Accepts an arbitrary Vin_diff so the same engine is used for both 1mV and 1µV cases.
"""

import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ── Locate the skill assets directory ────────────────────────────────────────
_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import (
    LOG_DIR, MODEL_DIR, NETLIST_DIR, NETLIST_SAVE_DIR,
    render_template, run_ngspice, parse_wrdata, spath,
)
from comparator_common import VDD, VCM, TCLK, W, L_NM, NOISE_NT, NOISE_NA

MODEL_PATH  = spath(MODEL_DIR / "ptm45hp.lib")
WAVE_VIN_MV = 1.0
WAVE_NCYC   = 3
WAVE_TSTOP  = WAVE_NCYC * TCLK
WAVE_TSTEP  = 2e-12   # 2 ps — smooth edges


# ─────────────────────────────────────────────────────────────────────────────
# DUT rendering helpers
# ─────────────────────────────────────────────────────────────────────────────
def _render_dut(tmpl_name, save_name):
    text = render_template(
        tmpl_name,
        L       = f"{L_NM}n",
        W_tail  = W["tail"],
        W_in    = W["inp"],
        W_lat_n = W["lat_n"],
        W_lat_p = W["lat_p"],
        W_rst   = W["rst"],
        W_inv_p = W["inv_p"],
        W_inv_n = W["inv_n"],
    )
    dut_path = NETLIST_SAVE_DIR / save_name
    dut_path.write_text(text, encoding="utf-8")
    return f".include {spath(dut_path)}", None


def _common_kw(dut_include):
    return dict(
        VDD         = VDD,
        noise_na    = f"{NOISE_NA:.6e}",
        noise_nt    = f"{NOISE_NT:.4e}",
        noise_na_uv = NOISE_NA * 1e6,
        noise_nt_ps = NOISE_NT * 1e12,
        model_path  = MODEL_PATH,
        dut_include = dut_include,
    )


def _run_netlist(tmpl_name, kw, log_path):
    text = render_template(tmpl_name, **kw)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cir", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp = f.name
    try:
        return run_ngspice(tmp, log=log_path, timeout=120)
    finally:
        os.unlink(tmp)


def _load(path):
    d = parse_wrdata(path) if path.exists() else None
    return (d[:, 0], d[:, 1]) if d is not None and len(d) > 10 else (None, None)


# ─────────────────────────────────────────────────────────────────────────────
# StrongArm waveform
# ─────────────────────────────────────────────────────────────────────────────
def _sim_strongarm(vin_mv):
    tag = f"compare_sa_{vin_mv:+.6g}mv".replace("+", "p").replace("-", "n").replace(".", "p")
    print(f"  [StrongArm Vin={vin_mv:+g}mV] starting ...", flush=True)
    t0 = time.perf_counter()

    dut_include, dut_tmp = _render_dut("comparator_strongarm.cir.tmpl",
                                        "comparator_strongarm_dut.cir")
    vin = vin_mv * 1e-3

    paths = {sig: LOG_DIR / f"{tag}_{sig}.txt"
             for sig in ("clk", "inp", "inn", "vxp", "vxn", "vlp", "vln", "outp", "outn")}
    log = LOG_DIR / f"{tag}.log"

    kw = dict(
        **_common_kw(dut_include),
        vin_label = vin_mv,
        vinp_dc   = VCM + vin / 2,
        vinn_dc   = VCM - vin / 2,
        tstep     = f"{WAVE_TSTEP:.4e}",
        tstop     = f"{WAVE_TSTOP:.4e}",
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    try:
        rc = _run_netlist("testbench_cmp_tran.cir.tmpl", kw, log)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    elapsed = time.perf_counter() - t0
    print(f"  [StrongArm Vin={vin_mv:+g}mV] exit {rc}, {elapsed:.1f}s", flush=True)

    t, clk  = _load(paths["clk"])
    _, inp  = _load(paths["inp"])
    _, inn  = _load(paths["inn"])
    _, vxp  = _load(paths["vxp"])
    _, vxn  = _load(paths["vxn"])
    _, vlp  = _load(paths["vlp"])
    _, vln  = _load(paths["vln"])
    _, outp = _load(paths["outp"])
    _, outn = _load(paths["outn"])

    return dict(topo="StrongArm", rc=rc, vin_mv=vin_mv,
                time=t, clk=clk, inp=inp, inn=inn,
                vxp=vxp, vxn=vxn,
                vlp=vlp, vln=vln,
                outp=outp, outn=outn)


# ─────────────────────────────────────────────────────────────────────────────
# Miyahara waveform
# ─────────────────────────────────────────────────────────────────────────────
def _sim_miyahara(vin_mv):
    tag = f"compare_miy_{vin_mv:+.6g}mv".replace("+", "p").replace("-", "n").replace(".", "p")
    print(f"  [Miyahara  Vin={vin_mv:+g}mV] starting ...", flush=True)
    t0 = time.perf_counter()

    dut_include, dut_tmp = _render_dut("comparator_miyahara.cir.tmpl",
                                        "comparator_miyahara_dut.cir")
    vin = vin_mv * 1e-3

    paths = {sig: LOG_DIR / f"{tag}_{sig}.txt"
             for sig in ("clk", "inp", "inn", "vlp", "vln", "outp", "outn")}
    log = LOG_DIR / f"{tag}.log"

    kw = dict(
        **_common_kw(dut_include),
        vin_label = vin_mv,
        vinp_dc   = VCM + vin / 2,
        vinn_dc   = VCM - vin / 2,
        tstep     = f"{WAVE_TSTEP:.4e}",
        tstop     = f"{WAVE_TSTOP:.4e}",
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    try:
        rc = _run_netlist("testbench_miyahara_tran.cir.tmpl", kw, log)
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    elapsed = time.perf_counter() - t0
    print(f"  [Miyahara ] exit {rc}, {elapsed:.1f}s", flush=True)

    t, clk  = _load(paths["clk"])
    _, inp  = _load(paths["inp"])
    _, inn  = _load(paths["inn"])
    _, vlp  = _load(paths["vlp"])
    _, vln  = _load(paths["vln"])
    _, outp = _load(paths["outp"])
    _, outn = _load(paths["outn"])

    elapsed = time.perf_counter() - t0
    print(f"  [Miyahara  Vin={vin_mv:+g}mV] exit {rc}, {elapsed:.1f}s", flush=True)

    return dict(topo="Miyahara", rc=rc, vin_mv=vin_mv,
                time=t, clk=clk, inp=inp, inn=inn,
                vxp=None, vxn=None,
                vlp=vlp, vln=vln,
                outp=outp, outn=outn)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def simulate_both(vin_mv):
    """Run SA and Miyahara in parallel for given Vin_diff [mV]. Returns (sa, miy)."""
    print(f"\n=== Waveform Comparison: StrongArm vs Miyahara  Vin={vin_mv:+g}mV, 3 cycles ===")
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_sa  = pool.submit(_sim_strongarm, vin_mv)
        f_miy = pool.submit(_sim_miyahara,  vin_mv)
        sa  = f_sa.result()
        miy = f_miy.result()
    return sa, miy
