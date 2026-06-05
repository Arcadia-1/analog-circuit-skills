#!/usr/bin/env python3
"""Output noise simulation for the two-stage op amp."""

import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from opamp_common import common_kw, params, render_dut, run_netlist

NOISE_PTS = 80
FSTART = 1.0
FSTOP = 100e6
F_INTEG_LO = 10.0
F_INTEG_HI = 10e6


def simulate_noise():
    print("\n=== Two-Stage Op Amp Noise Analysis ===")
    dut = render_dut()
    paths = {
        "freq": LOG_DIR / "opamp_noise_freq.txt",
        "onoise": LOG_DIR / "opamp_noise_onoise.txt",
        "inoise": LOG_DIR / "opamp_noise_inoise.txt",
        "cl_freq": LOG_DIR / "opamp_noise_unity_freq.txt",
        "cl_onoise": LOG_DIR / "opamp_noise_unity_onoise.txt",
        "cl_inoise": LOG_DIR / "opamp_noise_unity_inoise.txt",
    }
    kw = dict(
        **common_kw(dut),
        noise_pts=NOISE_PTS,
        fstart=f"{FSTART:.6g}",
        fstop=f"{FSTOP:.6g}",
        out_freq=spath(paths["freq"]),
        out_onoise=spath(paths["onoise"]),
        out_inoise=spath(paths["inoise"]),
    )
    rc = run_netlist("testbench_opamp_noise.cir.tmpl", kw, "opamp_noise.log")
    kw_cl = dict(
        **common_kw(dut),
        noise_pts=NOISE_PTS,
        fstart=f"{FSTART:.6g}",
        fstop=f"{FSTOP:.6g}",
        out_freq=spath(paths["cl_freq"]),
        out_onoise=spath(paths["cl_onoise"]),
        out_inoise=spath(paths["cl_inoise"]),
    )
    rc_cl = run_netlist("testbench_opamp_noise_unity.cir.tmpl", kw_cl, "opamp_noise_unity.log")

    def load(key):
        d = parse_wrdata(paths[key])
        return d[:, 1] if d is not None else None

    freq = load("freq")
    onoise = load("onoise")
    inoise = load("inoise")
    cl_freq = load("cl_freq")
    cl_onoise = load("cl_onoise")
    cl_inoise = load("cl_inoise")
    metrics = {}
    if freq is not None and onoise is not None:
        vn = np.abs(onoise)
        for f, name in [(1e3, "vn_1k_nvrtHz"), (10e3, "vn_10k_nvrtHz"), (1e6, "vn_1m_nvrtHz")]:
            metrics[name] = float(np.interp(f, freq, vn)) * 1e9
        mask = (freq >= F_INTEG_LO) & (freq <= F_INTEG_HI)
        if mask.sum() > 1:
            metrics["vn_rms_uv"] = float(np.sqrt(np.trapezoid(vn[mask] ** 2, freq[mask]))) * 1e6
        print(f"  [noise] Vn @ 1 kHz = {metrics.get('vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz")
        print(f"  [noise] Vn_rms ({F_INTEG_LO:.0f} Hz-{F_INTEG_HI/1e6:.0f} MHz) = "
              f"{metrics.get('vn_rms_uv', float('nan')):.2f} uV_rms")
    if freq is not None and inoise is not None:
        en = np.abs(inoise)
        metrics["en_1k_nvrtHz"] = float(np.interp(1e3, freq, en)) * 1e9
        mask = (freq >= F_INTEG_LO) & (freq <= F_INTEG_HI)
        if mask.sum() > 1:
            metrics["en_rms_uv"] = float(np.sqrt(np.trapezoid(en[mask] ** 2, freq[mask]))) * 1e6
        print(f"  [noise] input-referred en @ 1 kHz = "
              f"{metrics.get('en_1k_nvrtHz', float('nan')):.2f} nV/rtHz")
    if cl_freq is not None and cl_onoise is not None:
        cl_vn = np.abs(cl_onoise)
        metrics["cl_vn_1k_nvrtHz"] = float(np.interp(1e3, cl_freq, cl_vn)) * 1e9
        mask = (cl_freq >= F_INTEG_LO) & (cl_freq <= F_INTEG_HI)
        if mask.sum() > 1:
            metrics["cl_vn_rms_uv"] = float(np.sqrt(np.trapezoid(cl_vn[mask] ** 2, cl_freq[mask]))) * 1e6
        print(f"  [noise] unity closed-loop Vn @ 1 kHz = "
              f"{metrics.get('cl_vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz")
        print(f"  [noise] unity closed-loop Vn_rms = "
              f"{metrics.get('cl_vn_rms_uv', float('nan')):.2f} uV_rms")

    return {
        "noise": {
            "freq": freq,
            "onoise": onoise,
            "inoise": inoise,
            "cl_freq": cl_freq,
            "cl_onoise": cl_onoise,
            "cl_inoise": cl_inoise,
        },
        "metrics": metrics,
        "rc": rc,
        "rc_cl": rc_cl,
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
