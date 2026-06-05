#!/usr/bin/env python3
"""Output noise simulation for the five-transistor OTA."""

import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ota_common import common_kw, params, render_dut, run_netlist

NOISE_PTS = 80
FSTART = 1.0
FSTOP = 100e6
F_INTEG_LO = 10.0
F_INTEG_HI = 1e6


def simulate_noise():
    print("\n=== Five-Transistor OTA Noise Analysis ===")
    dut = render_dut()
    paths = {
        "freq": LOG_DIR / "ota_noise_freq.txt",
        "onoise": LOG_DIR / "ota_noise_onoise.txt",
    }
    kw = dict(
        **common_kw(dut),
        noise_pts=NOISE_PTS,
        fstart=f"{FSTART:.6g}",
        fstop=f"{FSTOP:.6g}",
        out_freq=spath(paths["freq"]),
        out_onoise=spath(paths["onoise"]),
    )
    rc = run_netlist("testbench_ota_noise.cir.tmpl", kw, "ota_noise.log")

    def load(key):
        d = parse_wrdata(paths[key])
        return d[:, 1] if d is not None else None

    freq = load("freq")
    onoise = load("onoise")
    metrics = {}
    if freq is not None and onoise is not None:
        vn = np.abs(onoise)
        for f, name in [(1e3, "vn_1k_nvrtHz"), (10e3, "vn_10k_nvrtHz")]:
            metrics[name] = float(np.interp(f, freq, vn)) * 1e9
        mask = (freq >= F_INTEG_LO) & (freq <= F_INTEG_HI)
        if mask.sum() > 1:
            metrics["vn_rms_uv"] = float(np.sqrt(np.trapezoid(vn[mask] ** 2, freq[mask]))) * 1e6
        print(f"  [noise] Vn @ 1 kHz = {metrics.get('vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz")
        print(f"  [noise] Vn_rms ({F_INTEG_LO:.0f} Hz-{F_INTEG_HI/1e6:.0f} MHz) = "
              f"{metrics.get('vn_rms_uv', float('nan')):.2f} uV_rms")

    return {
        "noise": {"freq": freq, "onoise": onoise},
        "metrics": metrics,
        "rc": rc,
        "params": params({
            "NOISE_PTS": NOISE_PTS,
            "FSTART": FSTART,
            "FSTOP": FSTOP,
            "F_INTEG_LO": F_INTEG_LO,
            "F_INTEG_HI": F_INTEG_HI,
        }),
    }


if __name__ == "__main__":
    simulate_noise()

