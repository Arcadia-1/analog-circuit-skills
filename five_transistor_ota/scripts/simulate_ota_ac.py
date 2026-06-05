#!/usr/bin/env python3
"""AC open-loop simulation for the five-transistor OTA."""

import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ota_common import common_kw, params, render_dut, run_netlist

AC_PTS = 100
FSTART = 1.0
FSTOP = 1e9


def _ugb(freq, gain_db):
    idx = np.where(gain_db <= 0)[0]
    if len(idx) == 0 or idx[0] == 0:
        return float("nan")
    i = int(idx[0])
    x0, x1 = np.log10(freq[i - 1]), np.log10(freq[i])
    y0, y1 = gain_db[i - 1], gain_db[i]
    return float(10 ** (x0 + (0 - y0) * (x1 - x0) / (y1 - y0)))


def simulate_ac():
    print("\n=== Five-Transistor OTA AC Analysis ===")
    dut = render_dut()
    paths = {
        "freq": LOG_DIR / "ota_ac_freq.txt",
        "gain_db": LOG_DIR / "ota_ac_gain_db.txt",
        "phase": LOG_DIR / "ota_ac_phase.txt",
    }
    kw = dict(
        **common_kw(dut),
        ac_pts=AC_PTS,
        fstart=f"{FSTART:.6g}",
        fstop=f"{FSTOP:.6g}",
        out_freq=spath(paths["freq"]),
        out_gain_db=spath(paths["gain_db"]),
        out_phase=spath(paths["phase"]),
    )
    rc = run_netlist("testbench_ota_ac.cir.tmpl", kw, "ota_ac.log")

    def load(key):
        d = parse_wrdata(paths[key])
        return d[:, 1] if d is not None else None

    freq = load("freq")
    gain_db = load("gain_db")
    phase_rad = load("phase")
    phase_deg = np.rad2deg(phase_rad) if phase_rad is not None else None

    metrics = {}
    if freq is not None and gain_db is not None:
        dc_gain_db = float(gain_db[0])
        ugb_hz = _ugb(freq, gain_db)
        phase_ugb_deg = float("nan")
        if phase_deg is not None and not np.isnan(ugb_hz):
            phase_ugb_deg = float(np.interp(np.log10(ugb_hz), np.log10(freq), phase_deg))
        metrics = {
            "dc_gain_db": dc_gain_db,
            "ugb_hz": ugb_hz,
            "phase_ugb_deg": phase_ugb_deg,
        }
        print(f"  [ac] DC gain = {dc_gain_db:.1f} dB")
        print(f"  [ac] UGB = {ugb_hz/1e6:.2f} MHz")
        print(f"  [ac] phase @ UGB = {phase_ugb_deg:.1f} deg")

    return {
        "ac": {"freq": freq, "gain_db": gain_db, "phase": phase_deg},
        "metrics": metrics,
        "rc": rc,
        "params": params({"AC_PTS": AC_PTS, "FSTART": FSTART, "FSTOP": FSTOP}),
    }


if __name__ == "__main__":
    simulate_ac()
