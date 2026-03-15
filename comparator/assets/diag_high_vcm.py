#!/usr/bin/env python3
"""
diag_high_vcm.py
================
Waveform diagnostic at two VCM values: 0.75V (good) vs 0.87V (broken).
No noise — clean DC input at +1mV to see if the circuit even resolves.
"""
import sys
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_ASSETS = Path(__file__).resolve().parent.parent / "comparator" / "assets"
sys.path.insert(0, str(_ASSETS))

from ngspice_common import LOG_DIR, PLOT_DIR, parse_wrdata, spath
from comparator_common import VDD, TCLK, render_dut, common_kw, run_netlist

VCM_VALS  = [0.60, 0.75, 0.82, 0.85, 0.87, 0.90]
VIN_MV    = 10.0   # large signal — rules out noise, tests polarity directly
NCYC      = 2
TSTEP     = 2e-12
TSTOP     = NCYC * TCLK


def _run(vcm, dut_include):
    tag   = f"diag_vcm{vcm*1000:.0f}mv"
    log   = LOG_DIR / f"{tag}.log"
    sigs  = ("clk", "inp", "inn", "vxp", "vxn", "vlp", "vln", "outp", "outn")
    paths = {s: LOG_DIR / f"{tag}_{s}.txt" for s in sigs}

    vin   = VIN_MV * 1e-3
    vinp  = vcm + vin / 2
    vinn  = vcm - vin / 2

    kw = dict(
        **common_kw(dut_include),
        vin_label = VIN_MV,
        vinp_dc   = vinp,
        vinn_dc   = vinn,
        tstep     = f"{TSTEP:.4e}",
        tstop     = f"{TSTOP:.4e}",
        **{f"out_{s}": spath(paths[s]) for s in sigs},
    )
    t0 = time.perf_counter()
    rc = run_netlist("testbench_cmp_tran.cir.tmpl", kw, log)
    print(f"  VCM={vcm:.2f}V  exit={rc}  {time.perf_counter()-t0:.1f}s", flush=True)

    def _load(k):
        d = parse_wrdata(paths[k]) if paths[k].exists() else None
        return (d[:, 0], d[:, 1]) if d is not None else (None, None)

    t, clk  = _load("clk")
    _, inp  = _load("inp")
    _, inn  = _load("inn")
    _, vxp  = _load("vxp")
    _, vxn  = _load("vxn")
    _, vlp  = _load("vlp")
    _, vln  = _load("vln")
    _, outp = _load("outp")
    _, outn = _load("outn")

    return dict(vcm=vcm, time=t, clk=clk, inp=inp, inn=inn,
                vxp=vxp, vxn=vxn, vlp=vlp, vln=vln, outp=outp, outn=outn)


def plot_diag(results):
    ncols = len(results)
    fig, axes = plt.subplots(3, ncols, figsize=(4 * ncols, 10), sharex="col")
    vcm_labels = "  |  ".join(f"{r['vcm']:.2f}V" for r in results)
    fig.suptitle(
        f"StrongArm Waveform Diagnostic — VIN=+{VIN_MV}mV, no noise\n"
        f"VCM: {vcm_labels}",
        fontsize=10, fontweight="bold"
    )

    row_labels = ["CLK + INP/INN", "VXP / VXN  (latch top)", "VLP/VLN + OUTP/OUTN"]

    for col, r in enumerate(results):
        t_ns = r["time"] * 1e9 if r["time"] is not None else None
        # Zoom into first evaluation window: CLK rises at ~0 + 5ps, eval phase = 500ps
        t_lo, t_hi = 0.0, 1.1   # ns

        ax0, ax1, ax2 = axes[0, col], axes[1, col], axes[2, col]
        vcm_str = f"VCM = {r['vcm']:.2f} V"

        # Row 0: CLK, INP, INN
        ax0.set_title(vcm_str, fontsize=10)
        if t_ns is not None:
            ax0.plot(t_ns, r["clk"], "k",   lw=1.2, label="CLK")
            ax0.plot(t_ns, r["inp"], "b--",  lw=1.0, label="INP")
            ax0.plot(t_ns, r["inn"], "r--",  lw=1.0, label="INN")
        ax0.set_ylabel(row_labels[0], fontsize=8)
        ax0.legend(fontsize=7, loc="upper right")
        ax0.set_ylim(-0.05, VDD * 1.15)
        ax0.grid(True, alpha=0.3)
        ax0.set_xlim(t_lo, t_hi)

        # Row 1: VXP, VXN
        if t_ns is not None:
            ax1.plot(t_ns, r["vxp"], "b", lw=1.2, label="VXP")
            ax1.plot(t_ns, r["vxn"], "r", lw=1.2, label="VXN")
        ax1.set_ylabel(row_labels[1], fontsize=8)
        ax1.legend(fontsize=7, loc="upper right")
        ax1.set_ylim(-0.05, VDD * 1.15)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(t_lo, t_hi)

        # Row 2: VLP, VLN, OUTP, OUTN
        if t_ns is not None:
            ax2.plot(t_ns, r["vlp"],  "b",   lw=1.2, label="VLP")
            ax2.plot(t_ns, r["vln"],  "r",   lw=1.2, label="VLN")
            ax2.plot(t_ns, r["outp"], "b--", lw=1.0, label="OUTP")
            ax2.plot(t_ns, r["outn"], "r--", lw=1.0, label="OUTN")
        ax2.set_ylabel(row_labels[2], fontsize=8)
        ax2.set_xlabel("Time (ns)", fontsize=8)
        ax2.legend(fontsize=7, loc="upper right")
        ax2.set_ylim(-0.05, VDD * 1.15)
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(t_lo, t_hi)

    plt.tight_layout()
    out = PLOT_DIR / "diag_high_vcm.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved -> {out}")


if __name__ == "__main__":
    print(f"\n=== VCM Diagnostic: {VCM_VALS} V, Vin=+{VIN_MV}mV, {NCYC} cycles ===\n")
    dut_include, dut_tmp = render_dut()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(_run, vcm, dut_include): vcm for vcm in VCM_VALS}
            results_map = {vcm: f.result() for f, vcm in
                           [(f, futures[f]) for f in futures]}
    finally:
        if dut_tmp: os.unlink(dut_tmp)

    results = [results_map[vcm] for vcm in VCM_VALS]
    plot_diag(results)
