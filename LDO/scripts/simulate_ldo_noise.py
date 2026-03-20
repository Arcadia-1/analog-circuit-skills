#!/usr/bin/env python3
"""
simulate_ldo_noise.py
=====================
Noise simulation: output-referred noise spectral density V(vout, vss).

Public API
----------
simulate_noise() -> dict
    'onoise'  : {freq, psd}   output noise density (V/rtHz) -- ngspice onoise_spectrum
    'metrics' : {vn_1k_nvrtHz, vn_10k_nvrtHz, vn_rms_uv}
    'params'  : circuit/sim parameters
"""

import time
import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ldo_common import (
    VIN_NOM, VREF_NOM, MODEL_PATH, R_LOAD_DEFAULT,
    circuit_params, render_dut, run_netlist,
)

# ── Noise sweep parameters ────────────────────────────────────────────────────
NOISE_PTS = 100          # points per decade
FSTART    = 1.0          # Hz
FSTOP     = 1e8          # Hz

# Integration band for RMS noise (typical LDO spec: 10 Hz – 100 kHz)
F_INTEG_LO = 10.0
F_INTEG_HI = 100e3


def simulate_noise() -> dict:
    """Run output noise analysis."""
    print("\n=== LDO Noise Simulation ===")
    dut_include, _ = render_dut()
    return _run_noise(dut_include)


def _run_noise(dut_include):
    tag = "ldo_noise"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log = LOG_DIR / f"{tag}.log"
    paths = {
        "noise_freq": LOG_DIR / f"{tag}_freq.txt",
        "onoise":     LOG_DIR / f"{tag}_onoise.txt",
    }

    kw = dict(
        vin_dc      = VIN_NOM,
        vref_dc     = VREF_NOM,
        r_load      = R_LOAD_DEFAULT,
        noise_pts   = NOISE_PTS,
        fstart      = f"{FSTART:.6g}",
        fstop       = f"{FSTOP:.6g}",
        dut_include = dut_include,
        model_path  = MODEL_PATH,
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_ldo_noise.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        d = parse_wrdata(paths[key])
        return d[:, 1] if d is not None else None

    freq   = _load("noise_freq")
    onoise = _load("onoise")    # V/rtHz  (ngspice onoise_spectrum is amplitude density)

    metrics = _extract_metrics(freq, onoise)
    return {
        "onoise":  {"freq": freq, "psd": onoise},
        "metrics": metrics,
        "rc":      rc,
        "elapsed": elapsed,
        "params":  circuit_params({
            "NOISE_PTS": NOISE_PTS,
            "FSTART":    FSTART,
            "FSTOP":     FSTOP,
            "F_INTEG_LO": F_INTEG_LO,
            "F_INTEG_HI": F_INTEG_HI,
        }),
    }


def _extract_metrics(freq, onoise):
    metrics = {}
    if freq is None or onoise is None:
        return metrics

    # ngspice onoise_spectrum is already V/sqrt(Hz) — no sqrt needed
    vn = np.abs(onoise)

    # Spot noise at 1 kHz and 10 kHz  (nV/sqrt(Hz))
    for f_spot, key in [(1e3, "vn_1k_nvrtHz"), (10e3, "vn_10k_nvrtHz")]:
        if freq[0] <= f_spot <= freq[-1]:
            val = float(np.interp(f_spot, freq, vn)) * 1e9
            metrics[key] = val
            print(f"  [noise] Vn @ {f_spot/1e3:.0f} kHz = {val:.2f} nV/rtHz", flush=True)

    # Integrated RMS noise over F_INTEG_LO to F_INTEG_HI
    mask = (freq >= F_INTEG_LO) & (freq <= F_INTEG_HI)
    if mask.sum() > 1:
        # onoise is V/rtHz; integrate power (onoise²) then sqrt for Vrms
        vn_rms = float(np.sqrt(np.trapezoid(np.abs(onoise[mask])**2, freq[mask]))) * 1e6
        metrics["vn_rms_uv"] = vn_rms
        print(f"  [noise] Vn_rms ({F_INTEG_LO:.0f} Hz-{F_INTEG_HI/1e3:.0f} kHz) = {vn_rms:.2f} uV_rms",
              flush=True)

    # 1/f corner: find the thermal-noise flat region between the 1/f rise and loop-BW roll-off,
    # then find where 1/f noise equals the thermal floor (from high-freq side, scanning downward).
    # Strategy: flat floor = median of vn in [1% of FSTOP … 10% of FSTOP] (above loop BW but
    # below high-freq rolloff); corner = lowest frequency where vn > sqrt(2)*floor.
    f_floor_lo = FSTOP * 0.001   # 100 kHz for FSTOP=100 MHz
    f_floor_hi = FSTOP * 0.01    # 1 MHz
    mask_floor = (freq >= f_floor_lo) & (freq <= f_floor_hi)
    if mask_floor.sum() > 3:
        vn_floor = float(np.median(vn[mask_floor]))
        metrics["vn_floor_nvrtHz"] = vn_floor * 1e9
        # scan from high freq downward; 1/f corner = where vn first exceeds sqrt(2)*floor
        above = vn > vn_floor * np.sqrt(2)
        idx = np.where(above & (freq < f_floor_lo))[0]
        if len(idx) > 0:
            corner = float(freq[idx[-1]])
            metrics["flicker_corner_hz"] = corner
            print(f"  [noise] thermal floor ~ {vn_floor*1e9:.1f} nV/rtHz  "
                  f"1/f corner ~ {corner:.0f} Hz", flush=True)

    return metrics
