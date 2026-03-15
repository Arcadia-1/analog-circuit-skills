#!/usr/bin/env python3
"""
comparator_common.py
====================
Shared circuit parameters, DUT rendering, and helper functions for all
StrongArm comparator simulation scripts.

Imported by:
  simulate_tran_strongarm_wave.py
  simulate_tran_strongarm_noise.py
  simulate_tran_strongarm_ramp.py
"""

import tempfile
import os
from pathlib import Path
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import erfc
from scipy.stats import norm as _norm

from ngspice_common import (
    LOG_DIR, MODEL_DIR, NETLIST_SAVE_DIR,
    render_template, run_ngspice, parse_wrdata, spath,
)

# ─────────────────────────────────────────────────────────────────────────────
# Circuit / technology parameters
# ─────────────────────────────────────────────────────────────────────────────
VDD   = 1.0        # V  (45nm HP nominal supply)
VCM   = VDD / 2    # V  common-mode input

FCLK  = 1e9        # Hz  1 GHz clock
TCLK  = 1 / FCLK   # s   1 ns period

# trnoise injection at INP/INN — band-limited to 100 GHz
# Amplitude is a stimulus parameter; true sigma_n is extracted by CDF fit.
# High BW (short NT) ensures noise is decorrelated between 1 GHz clock cycles.
NOISE_BW = 100e9             # Hz
NOISE_NT = 1 / (2 * NOISE_BW)   # 5 ps  (noise update interval)
NOISE_NA = 300e-6            # V per side

L_NM = 45   # nm  (45nm PTM HP)

W = dict(
    tail  = 4.0,   # tail NMOS (M0)
    inp   = 4.0,   # input NMOS pair (M1, M2)
    lat_n = 1.0,   # latch NMOS (M3, M4)
    lat_p = 2.0,   # latch PMOS cross-coupled (M5, M6)
    rst   = 1.0,   # reset PMOS (M7-M10)
    inv_p = 2.0,   # output inverter PMOS
    inv_n = 1.0,   # output inverter NMOS
)

MODEL_PATH   = spath(MODEL_DIR / "ptm45hp.lib")
NOISE_VIN_MV = 0.35  # fixed differential (mV) for single-point noise extraction
              # ≈ 1σ → P(1) ≈ 84%, optimal statistical efficiency for probit method

# Sampling instant: 45% into the CLK high phase (after comparison settles)
SAMPLE_OFFSET = 0.45 * (TCLK / 2)   # 0.225 ns after CLK rises


def circuit_params(extra=None):
    """Return base circuit parameter dict (for plot titles and FOM log)."""
    p = dict(
        VDD          = VDD,
        VCM          = VCM,
        FCLK         = FCLK,
        NOISE_BW_GHZ = NOISE_BW / 1e9,
        NOISE_NA_UV  = NOISE_NA * 1e6,
        L_NM         = L_NM,
        W            = W,
    )
    if extra:
        p.update(extra)
    return p


# ─────────────────────────────────────────────────────────────────────────────
# DUT rendering
# ─────────────────────────────────────────────────────────────────────────────
def render_dut() -> tuple:
    """
    Render comparator_strongarm.cir.tmpl → netlists/comparator_strongarm_dut.cir.

    The DUT parameters are all globals (L, W dict), so the rendered content is
    identical on every call.  Writing to a fixed path avoids littering /tmp with
    random-named files and makes the netlist inspectable at any time.

    Returns (include_line_str, None).
    Callers must NOT os.unlink() the second return value.
    """
    from ngspice_common import NETLIST_SAVE_DIR
    text = render_template(
        "comparator_strongarm.cir.tmpl",
        L       = f"{L_NM}n",
        W_tail  = W["tail"],
        W_in    = W["inp"],
        W_lat_n = W["lat_n"],
        W_lat_p = W["lat_p"],
        W_rst   = W["rst"],
        W_inv_p = W["inv_p"],
        W_inv_n = W["inv_n"],
    )
    dut_path = NETLIST_SAVE_DIR / "comparator_strongarm_dut.cir"
    dut_path.write_text(text, encoding="utf-8")
    return f".include {spath(dut_path)}", None


def common_kw(dut_include: str) -> dict:
    """Keyword args shared by all testbench templates."""
    return dict(
        VDD         = VDD,
        noise_na    = f"{NOISE_NA:.6e}",
        noise_nt    = f"{NOISE_NT:.4e}",
        noise_na_uv = NOISE_NA * 1e6,
        noise_nt_ps = NOISE_NT * 1e12,
        model_path  = MODEL_PATH,
        dut_include = dut_include,
    )


def run_netlist(tmpl_name, kw, log_path, timeout=600):
    """Render testbench template, save to netlists/, run ngspice, return exit code."""
    text = render_template(tmpl_name, **kw)
    # Save a human-readable copy alongside the log
    save_path = NETLIST_SAVE_DIR / (Path(log_path).stem + ".cir")
    save_path.write_text(text, encoding="utf-8")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cir", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        tmp = f.name
    try:
        return run_ngspice(tmp, log=log_path, timeout=timeout)
    finally:
        os.unlink(tmp)


# ─────────────────────────────────────────────────────────────────────────────
# Signal processing helpers
# ─────────────────────────────────────────────────────────────────────────────
def sample_output(time_arr, outp_arr, ncyc, sample_offset=None):
    """
    Sample OUTP at a fixed offset into each clock high phase.
    Returns int array of length ncyc with values in {0, 1}.
    """
    if sample_offset is None:
        sample_offset = SAMPLE_OFFSET
    t_sample = np.arange(ncyc) * TCLK + sample_offset
    outp_s = np.interp(t_sample, time_arr, outp_arr)
    return (outp_s > VDD / 2).astype(int)


def compute_tau_from_latch(time_arr, vlp_arr, vln_arr, ncyc):
    """
    Extract latch regeneration time constant τ from VLP/VLN waveforms.

    During regeneration vdiff = |VLN - VLP| grows exponentially.
    Two-threshold crossing:  τ = (t_hi - t_lo) / ln(V_hi / V_lo)

    v_lo = 0.05 * VDD  — above noise floor
    v_hi = 0.40 * VDD  — well below saturation

    Returns mean τ in ps across valid cycles, or nan if extraction fails.
    """
    v_lo = 0.05 * VDD
    v_hi = 0.40 * VDD
    tau_list = []

    for n in range(ncyc):
        # Search from 10 ps after CLK rise (CLK TR=10ps, fully high by 10ps)
        # to 92% into the clock period (accommodates slow-resolving corners).
        # Must NOT start at 50ps — fast circuits (large W_inp) can fire before 50ps.
        t_start = n * TCLK + 10e-12
        t_end   = n * TCLK + 0.92 * TCLK

        mask  = (time_arr >= t_start) & (time_arr < t_end)
        t_win = time_arr[mask]
        vdiff = np.abs(vln_arr[mask] - vlp_arr[mask])

        if len(t_win) < 4:
            continue

        # First upward crossing of v_lo
        t_lo = None
        for i in range(len(vdiff) - 1):
            if vdiff[i] < v_lo <= vdiff[i + 1]:
                frac = (v_lo - vdiff[i]) / (vdiff[i + 1] - vdiff[i])
                t_lo = t_win[i] + frac * (t_win[i + 1] - t_win[i])
                break

        if t_lo is None:
            continue

        # First upward crossing of v_hi after t_lo
        t_hi = None
        for i in range(len(vdiff) - 1):
            if t_win[i] < t_lo:
                continue
            if vdiff[i] < v_hi <= vdiff[i + 1]:
                frac = (v_hi - vdiff[i]) / (vdiff[i + 1] - vdiff[i])
                t_hi = t_win[i] + frac * (t_win[i + 1] - t_win[i])
                break

        if t_hi is None:
            continue

        tau = (t_hi - t_lo) / np.log(v_hi / v_lo)
        if tau > 0:
            tau_list.append(tau)

    if not tau_list:
        return float("nan")
    return float(np.mean(tau_list)) * 1e12   # → ps


def compute_tcmp(time_arr, outp_arr, ncyc):
    """
    Measure Tcmp by averaging CLK→OUTP crossing times across ncyc cycles.

    CLK is PULSE(0 VDD 0 10p 10p 500p 1n): crosses VDD/2 at n*TCLK + 5ps.
    Skips cycles where OUTP stays LOW (comparator resolved LOW).
    Returns mean Tcmp [ps], or nan if no valid cycles.
    """
    half = VDD / 2
    clk_rise_half = 5e-12    # TR/2 = 5 ps
    tcmp_list = []

    for n in range(ncyc):
        t_clk = n * TCLK + clk_rise_half
        t_end = t_clk + 0.9 * TCLK

        mask  = (time_arr >= t_clk) & (time_arr <= t_end)
        t_win = time_arr[mask]
        o_win = outp_arr[mask]

        if len(t_win) < 2:
            continue

        for i in range(len(o_win) - 1):
            if o_win[i] < half <= o_win[i + 1]:
                frac    = (half - o_win[i]) / (o_win[i + 1] - o_win[i])
                t_cross = t_win[i] + frac * (t_win[i + 1] - t_win[i])
                tcmp_list.append(t_cross - t_clk)
                break

    if not tcmp_list:
        return float("nan")
    return float(np.mean(tcmp_list)) * 1e12   # ps


# ─────────────────────────────────────────────────────────────────────────────
# Transfer curve fitting
# ─────────────────────────────────────────────────────────────────────────────
def _gauss_cdf(vin, mu, sigma):
    return 0.5 * erfc(-(vin - mu) / (sigma * np.sqrt(2)))


def fit_transfer_curve(sweep) -> dict:
    """
    Fit P(1) vs Vin to a Gaussian CDF with mu pinned to 0.

    mu is fixed at 0 — pre-layout simulation uses a symmetric circuit so
    any apparent offset is a finite-sample artifact, not a real offset.

    Parameters
    ----------
    sweep : list of dicts with keys {vin_mv, p1}

    Returns
    -------
    dict: mu_v, sigma_v, mu_uv, sigma_uv, vin_arr, p1_arr, p1_fit, fit_ok, perr
          perr[0] = 0.0 (mu fixed), perr[1] = 1-sigma uncertainty on sigma_v
    """
    vin_arr = np.array([r["vin_mv"] * 1e-3 for r in sweep])
    p1_arr  = np.array([r["p1"]            for r in sweep])

    p0_sig = 500e-6

    fit_ok = False
    sigma_v = p0_sig
    pcov_sig = np.nan

    try:
        popt, pcov = curve_fit(
            lambda vin, sigma: _gauss_cdf(vin, 0.0, sigma),
            vin_arr, p1_arr,
            p0=[p0_sig],
            bounds=([50e-6], [5e-3]),
            maxfev=5000,
        )
        sigma_v  = popt[0]
        pcov_sig = pcov[0, 0]
        fit_ok = True
    except Exception as e:
        print(f"  [fit] WARNING: curve_fit failed: {e}")

    mu_v = 0.0
    perr = np.array([0.0, np.sqrt(pcov_sig) if fit_ok else np.nan])
    p1_fit = _gauss_cdf(vin_arr, 0.0, abs(sigma_v))

    return dict(
        mu_v     = mu_v,
        sigma_v  = abs(sigma_v),
        mu_uv    = mu_v * 1e6,
        sigma_uv = abs(sigma_v) * 1e6,
        vin_arr  = vin_arr,
        p1_arr   = p1_arr,
        p1_fit   = p1_fit,
        fit_ok   = fit_ok,
        perr     = perr,
    )


def sigma_from_p1(p1, vin_v):
    """
    Compute input-referred noise sigma from a single (Vin, P1) measurement.

    Formula:  sigma = vin_v / Phi^{-1}(P1)

    where mu = 0 (symmetric pre-layout circuit) and Phi^{-1} is the
    inverse normal CDF (probit function).

    Parameters
    ----------
    p1    : float  P(output=1), must be in (0.5, 1.0)
    vin_v : float  fixed differential input voltage in Volts (> 0)

    Returns
    -------
    float : sigma_n in Volts, or nan if inputs are out of range
    """
    if not (0.5 < p1 < 1.0) or vin_v <= 0:
        return float("nan")
    return vin_v / _norm.ppf(p1)
