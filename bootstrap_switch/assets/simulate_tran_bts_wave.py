#!/usr/bin/env python3
"""
simulate_tran_bts_wave.py
=========================
Transient waveform simulation: CLK, VIN (sine), VGATE, VSAMPLED, CB nodes.
Shows the bootstrap mechanism in action over several clock cycles.
"""

import time
import numpy as np

from bootstrap_common import (
    LOG_DIR, VDD, FCLK, TCLK, CS,
    render_dut, common_kw, run_netlist, parse_wrdata, spath,
    circuit_params,
)

WAVE_NCYC  = 8       # clock cycles to simulate
WAVE_TSTOP = WAVE_NCYC * TCLK
WAVE_TSTEP = 100e-12  # 100 ps

# Input sine: frequency = FCLK/8 (one full sine period over 8 CLK cycles)
FIN   = FCLK / WAVE_NCYC
VCM   = VDD / 2
VAMP  = (VDD / 2) * 0.95   # nearly full swing


def simulate_wave():
    """Run waveform transient and return dict with all signals."""
    print(f"\n=== Bootstrap Switch Waveform ({WAVE_NCYC} cycles) ===")
    t0 = time.perf_counter()

    dut_include, _ = render_dut()

    paths = {sig: LOG_DIR / f"bts_wave_{sig}.txt"
             for sig in ("clk", "vin", "vgate", "vsampled", "cbtop", "cbbot")}

    kw = dict(
        **common_kw(dut_include),
        vcm       = VCM,
        vamp      = VAMP,
        fin       = f"{FIN:.4e}",
        tstep     = f"{WAVE_TSTEP:.4e}",
        tstop     = f"{WAVE_TSTOP:.4e}",
        out_clk      = spath(paths["clk"]),
        out_vin      = spath(paths["vin"]),
        out_vgate    = spath(paths["vgate"]),
        out_vsampled = spath(paths["vsampled"]),
        out_cbtop    = spath(paths["cbtop"]),
        out_cbbot    = spath(paths["cbbot"]),
    )

    log = LOG_DIR / "bts_wave.log"
    rc = run_netlist("testbench_bts_tran.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0

    print(f"  ngspice exit {rc}, {elapsed:.1f}s")

    def _load(key):
        p = paths[key]
        d = parse_wrdata(p) if p.exists() else None
        return (d[:, 0], d[:, 1]) if d is not None else (None, None)

    t, clk       = _load("clk")
    _, vin       = _load("vin")
    _, vgate     = _load("vgate")
    _, vsampled  = _load("vsampled")
    _, cbtop     = _load("cbtop")
    _, cbbot     = _load("cbbot")

    # Compute bootstrap voltage
    vboost = None
    if vgate is not None and vin is not None:
        vboost = vgate - vin

    return {
        "time": t, "clk": clk, "vin": vin,
        "vgate": vgate, "vsampled": vsampled,
        "cbtop": cbtop, "cbbot": cbbot,
        "vboost": vboost,
        "params": circuit_params({"WAVE_NCYC": WAVE_NCYC, "FIN": FIN}),
        "rc": rc, "elapsed": elapsed,
    }
