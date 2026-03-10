#!/usr/bin/env python3
"""
simulate_tran_strongarm_comp.py
================================
Simulation engine for StrongArm dynamic comparator (45nm PTM HP).

Netlist structure (DUT / testbench separated)
---------------------------------------------
  comparator_strongarm.cir.tmpl     — DUT: .subckt (parameterized L, W)
  testbench_cmp_tran.cir.tmpl       — TB: 5-cycle waveform, all nodes + VDD current
  testbench_cmp_tran_noise.cir.tmpl — TB: N-cycle noise statistics (one Vin level)
  testbench_cmp_ramp.cir.tmpl       — TB: 100-cycle ramp input

Simulations (all in parallel)
------------------------------
  1. Waveform   : Vin=+1mV, 5 cycles, all internal nodes + VDD current
  2. Sweep      : 9 Vin levels (-2..+2 mV), SWEEP_NCYC cycles each -> P(1) per level
  3. Ramp       : Vin ramps -RAMP_VIN_END -> +RAMP_VIN_END over RAMP_NCYC cycles

Public API
----------
simulate_all() -> dict
    'wave'   : waveform result dict (time, clk, inp, inn, vxp, vxn, vlp, vln, outp, outn, ivdd)
    'sweep'  : list of sweep point dicts  {vin_mv, count_0, count_1, p1}
    'ramp'   : ramp result dict
    'params' : circuit/sim parameters

fit_transfer_curve(sweep) -> dict
    Fits P(1) vs Vin to a Gaussian CDF, returns:
    {mu_v, sigma_v, mu_uv, sigma_uv, vin_arr, p1_arr, p1_fit, fit_ok}

compute_fom(results) -> dict
    {sigma_uv, mu_uv, p_avg_uw, tcmp_ps, fom1, fom2}
    Writes logs/fom_report.txt
"""

import tempfile
import os
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from scipy.optimize import curve_fit
from scipy.special import erfc

from ngspice_common import (
    LOG_DIR, NETLIST_DIR, MODEL_DIR,
    render_template, run_ngspice, parse_wrdata, spath,
)

# ─────────────────────────────────────────────────────────────────────────────
# Circuit / technology parameters
# ─────────────────────────────────────────────────────────────────────────────
VDD   = 1.0      # V  (45nm HP nominal supply)
VCM   = VDD / 2  # V  common-mode input

# Clock: 1 GHz, 50% duty cycle
FCLK  = 1e9      # Hz
TCLK  = 1 / FCLK # s = 1 ns

# Injected noise: trnoise sources at INP/INN, band-limited to 10 GHz
# This is the simulation stimulus amplitude — NOT assumed to equal sigma_n.
# The true sigma_n is extracted by fitting the P(1) vs Vin transfer curve.
NOISE_BW    = 10e9              # Hz
NOISE_NT    = 1 / (2 * NOISE_BW)   # 50 ps  (noise update interval)
NOISE_NA    = 300e-6            # V per side amplitude (reasonable starting point)

# Channel length (nm) — matches the technology node / model file
L_NM = 45   # nm  (45nm PTM HP)

# Transistor W (um), L = L_NM for all devices
W = dict(
    tail  = 4.0,   # tail NMOS (M0)
    inp   = 4.0,   # input NMOS pair (M1, M2)
    lat_n = 1.0,   # latch NMOS (M3, M4) — source=VXP/VXN, gate=VLN/VLP (cross-coupled)
    lat_p = 2.0,   # latch PMOS cross-coupled (M5, M6)
    rst   = 1.0,   # reset PMOS (M7-M10)
    inv_p = 2.0,   # output inverter PMOS (M11, M13)
    inv_n = 1.0,   # output inverter NMOS (M12, M14)
)

MODEL_PATH = spath(MODEL_DIR / "ptm45hp.lib")

# ─────────────────────────────────────────────────────────────────────────────
# Simulation timing
# ─────────────────────────────────────────────────────────────────────────────
WAVE_TSTOP  = 3 * TCLK        # 3 ns — 3 cycles, internal node waveform
WAVE_TSTEP  = 10e-12           # 10 ps

# Sweep: 13 Vin levels, 1000 cycles each
# Range covers full 0→100% transition; ±2mV is safe for ~300-700 uV sigma
SWEEP_VIN_MV  = list(np.linspace(-1.5, 1.5, 13))   # mV, equally spaced
SWEEP_NCYC    = 1000
SWEEP_TSTOP   = SWEEP_NCYC * TCLK   # 500 ns
SWEEP_TSTEP   = 50e-12              # 50 ps

# Sampling instant: 45% into the high phase (before CLK falls, after comparison)
SAMPLE_OFFSET = 0.45 * (TCLK / 2)   # 0.225 ns after CLK rises

# Ramp: Vin ramps from -RAMP_VIN_END to +RAMP_VIN_END over RAMP_NCYC cycles
RAMP_NCYC       = 100
RAMP_TSTOP      = RAMP_NCYC * TCLK  # 100 ns
RAMP_TSTEP      = 50e-12
RAMP_VIN_START  = -2e-3   # V
RAMP_VIN_END    = +2e-3   # V


# ─────────────────────────────────────────────────────────────────────────────
# DUT rendering (shared temp file across all testbenches)
# ─────────────────────────────────────────────────────────────────────────────
def _render_dut() -> tuple:
    """
    Render comparator_strongarm.cir.tmpl with current W and L values.
    Returns (include_line_str, tmp_file_path_to_delete).
    """
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
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".cir", delete=False, encoding="utf-8"
    )
    f.write(text)
    f.close()
    return f".include {spath(f.name)}", f.name


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _common_kw(dut_include: str) -> dict:
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


def _run_netlist(tmpl_name, kw, log_path, timeout=600):
    """Render testbench template, write temp file, run ngspice, return exit code."""
    text = render_template(tmpl_name, **kw)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cir", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        tmp = f.name
    try:
        return run_ngspice(tmp, log=log_path, timeout=timeout)
    finally:
        os.unlink(tmp)


def _sample_output(time_arr, outp_arr, ncyc, sample_offset):
    """
    Sample OUTP at a fixed offset into each clock high phase.
    Returns int array of length ncyc with values in {0, 1}.
    """
    t_sample = np.arange(ncyc) * TCLK + sample_offset
    outp_s = np.interp(t_sample, time_arr, outp_arr)
    return (outp_s > VDD / 2).astype(int)


def _compute_tcmp_from_outp(time_arr, outp_arr, ncyc):
    """
    Measure Tcmp by averaging CLK→OUTP crossing times across all cycles.

    CLK is a PULSE(0 VDD 0 10p 10p 500p 1n) source, so its rising edge
    crosses VDD/2 analytically at t = n*TCLK + TR/2 = n*TCLK + 5ps.
    No need to save v(clk).

    For each cycle, find the first upward OUTP crossing of VDD/2 after the
    CLK rising edge.  Skip cycles where OUTP never crosses (resolved LOW).
    Returns mean Tcmp in ps, or nan if no valid cycles.
    """
    half = VDD / 2
    clk_rise_half = 5e-12      # TR/2 = 10ps/2 — CLK crosses VDD/2 here
    tcmp_list = []

    for n in range(ncyc):
        t_clk = n * TCLK + clk_rise_half
        t_end = t_clk + 0.9 * TCLK          # search within same clock period

        mask  = (time_arr >= t_clk) & (time_arr <= t_end)
        t_win = time_arr[mask]
        o_win = outp_arr[mask]

        if len(t_win) < 2:
            continue

        # First upward crossing of VDD/2
        for i in range(len(o_win) - 1):
            if o_win[i] < half <= o_win[i + 1]:
                frac    = (half - o_win[i]) / (o_win[i + 1] - o_win[i])
                t_cross = t_win[i] + frac * (t_win[i + 1] - t_win[i])
                tcmp_list.append(t_cross - t_clk)
                break

    if not tcmp_list:
        return float("nan")
    return float(np.mean(tcmp_list)) * 1e12   # → ps


# ─────────────────────────────────────────────────────────────────────────────
# Individual simulation tasks
# ─────────────────────────────────────────────────────────────────────────────
def _run_wave(vin_mv, dut_include):
    """Waveform simulation: 5 cycles, all internal nodes + VDD current."""
    tag = f"wave_vin{vin_mv:+.0f}mv"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    vin  = vin_mv * 1e-3
    log  = LOG_DIR / f"strongarm_{tag}.log"
    paths = {sig: LOG_DIR / f"strongarm_{tag}_{sig}.txt"
             for sig in ("clk", "inp", "inn", "vxp", "vxn", "vlp", "vln",
                         "outp", "outn", "ivdd")}

    kw = dict(
        **_common_kw(dut_include),
        vin_label = vin_mv,
        vinp_dc   = VCM + vin / 2,
        vinn_dc   = VCM - vin / 2,
        tstep     = f"{WAVE_TSTEP:.4e}",
        tstop     = f"{WAVE_TSTOP:.4e}",
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = _run_netlist("testbench_cmp_tran.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        p = paths[key]
        d = parse_wrdata(p) if p.exists() else None
        return (d[:, 0], d[:, 1]) if d is not None else (None, None)

    t, clk   = _load("clk")
    _, inp   = _load("inp")
    _, inn   = _load("inn")
    _, vxp   = _load("vxp")
    _, vxn   = _load("vxn")
    _, vlp   = _load("vlp")
    _, vln   = _load("vln")
    _, outp  = _load("outp")
    _, outn  = _load("outn")
    _, ivdd  = _load("ivdd")

    return {
        "type": "wave", "vin_mv": vin_mv, "rc": rc, "elapsed": elapsed,
        "time": t, "clk": clk, "inp": inp, "inn": inn,
        "vxp": vxp, "vxn": vxn, "vlp": vlp, "vln": vln,
        "outp": outp, "outn": outn, "ivdd": ivdd,
    }


def _run_sweep_point(vin_mv, dut_include):
    """
    One sweep point: simulate SWEEP_NCYC cycles at a fixed Vin level, count P(1).
    When vin_mv == 0, also saves i(vvdd) to a fixed log file for power extraction
    (overwritten each run — only one file, no accumulation).
    """
    tag  = f"sweep_vin{vin_mv:+.2f}mv"
    print(f"  [{tag}] starting ...", flush=True)
    t0   = time.perf_counter()

    vin  = vin_mv * 1e-3
    log  = LOG_DIR / f"strongarm_{tag}.log"
    out  = LOG_DIR / f"strongarm_{tag}_outp.txt"

    # Only measure power at Vin=0 (balanced input, most representative)
    measure_power = (vin_mv == 0.0)
    if measure_power:
        ivdd_path = LOG_DIR / "strongarm_sweep_vin0_ivdd.txt"
        ivdd_cmd  = f"wrdata {spath(ivdd_path)} i(vvdd)"
    else:
        ivdd_path = None
        ivdd_cmd  = ""   # no-op line in netlist

    kw = dict(
        **_common_kw(dut_include),
        vin_label = vin_mv,
        inp_src   = f"VINP_DC INP_DC 0 DC {VCM + vin/2:.10f}",
        inn_src   = f"VINN_DC INN_DC 0 DC {VCM - vin/2:.10f}",
        tstep     = f"{SWEEP_TSTEP:.4e}",
        tstop     = f"{SWEEP_TSTOP:.4e}",
        out_outp  = spath(out),
        ivdd_cmd  = ivdd_cmd,
    )
    rc = _run_netlist("testbench_cmp_tran_noise.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0

    raw = parse_wrdata(out) if out.exists() else None
    count_1 = count_0 = 0
    time_arr = outp_arr = None

    if raw is not None and len(raw) > 100:
        time_arr = raw[:, 0]
        outp_arr = raw[:, 1]
        samples  = _sample_output(time_arr, outp_arr, SWEEP_NCYC, SAMPLE_OFFSET)
        count_1  = int(np.sum(samples))
        count_0  = SWEEP_NCYC - count_1
    else:
        print(f"  [{tag}] WARNING: no usable data")

    p_avg_uw = float("nan")
    if measure_power and ivdd_path is not None and ivdd_path.exists():
        ivdd_raw = parse_wrdata(ivdd_path)
        if ivdd_raw is not None and len(ivdd_raw) > 100:
            p_avg_uw = VDD * np.mean(np.abs(ivdd_raw[:, 1])) * 1e6

    # Tcmp measured at Vin=+1mV: average CLK→OUTP crossing over 1000 cycles
    tcmp_ps = float("nan")
    if vin_mv == 1.0 and time_arr is not None:
        tcmp_ps = _compute_tcmp_from_outp(time_arr, outp_arr, SWEEP_NCYC)
        print(f"  [{tag}] Tcmp = {tcmp_ps:.1f} ps  (avg over {SWEEP_NCYC} cycles)", flush=True)

    p1 = count_1 / SWEEP_NCYC
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s | "
          f"Vin={vin_mv:+.2f}mV -> {count_1}/{SWEEP_NCYC} HIGH  "
          f"P(1)={p1*100:.1f}%", flush=True)

    return {
        "type": "sweep_pt", "vin_mv": vin_mv,
        "count_0": count_0, "count_1": count_1, "p1": p1,
        "p_avg_uw": p_avg_uw,
        "tcmp_ps": tcmp_ps,
        "rc": rc, "elapsed": elapsed,
    }


def _run_ramp(dut_include):
    """Ramp simulation: Vin goes RAMP_VIN_START -> RAMP_VIN_END over RAMP_NCYC cycles."""
    tag  = "ramp"
    print(f"  [{tag}] starting ...", flush=True)
    t0   = time.perf_counter()
    log  = LOG_DIR / "strongarm_ramp.log"
    out_outp = LOG_DIR / "strongarm_ramp_outp.txt"
    out_outn = LOG_DIR / "strongarm_ramp_outn.txt"
    out_inp  = LOG_DIR / "strongarm_ramp_inp.txt"
    out_inn  = LOG_DIR / "strongarm_ramp_inn.txt"

    vinp_start = VCM + RAMP_VIN_START / 2
    vinp_end   = VCM + RAMP_VIN_END   / 2
    vinn_start = VCM - RAMP_VIN_START / 2
    vinn_end   = VCM - RAMP_VIN_END   / 2

    kw = dict(
        **_common_kw(dut_include),
        vin_start_mv = RAMP_VIN_START * 1e3,
        vin_end_mv   = RAMP_VIN_END   * 1e3,
        n_cycles     = RAMP_NCYC,
        vinp_start   = f"{vinp_start:.10f}",
        vinp_end     = f"{vinp_end:.10f}",
        vinn_start   = f"{vinn_start:.10f}",
        vinn_end     = f"{vinn_end:.10f}",
        tstep        = f"{RAMP_TSTEP:.4e}",
        tstop        = f"{RAMP_TSTOP:.4e}",
        out_outp     = spath(out_outp),
        out_outn     = spath(out_outn),
        out_inp      = spath(out_inp),
        out_inn      = spath(out_inn),
    )
    rc = _run_netlist("testbench_cmp_ramp.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(p):
        d = parse_wrdata(p) if p.exists() else None
        return (d[:, 0], d[:, 1]) if d is not None and len(d) > 10 else (None, None)

    time_arr, outp_arr = _load(out_outp)
    _,        outn_arr = _load(out_outn)
    _,        inp_arr  = _load(out_inp)
    _,        inn_arr  = _load(out_inn)

    # Differential signals for plotting
    vout_diff = vin_diff = None
    if outp_arr is not None and outn_arr is not None:
        vout_diff = outp_arr - outn_arr          # V, swings ±VDD
    if inp_arr is not None and inn_arr is not None:
        vin_diff = (inp_arr - inn_arr) * 1e3     # mV

    return {
        "type": "ramp", "rc": rc, "elapsed": elapsed,
        "time": time_arr,
        "vout_diff": vout_diff,   # OUTP - OUTN [V]
        "vin_diff":  vin_diff,    # INP  - INN  [mV]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Transfer curve fitting
# ─────────────────────────────────────────────────────────────────────────────
def _gauss_cdf(vin, mu, sigma):
    """Gaussian CDF: P(output=1 | Vin) = Phi((Vin - mu) / sigma)."""
    return 0.5 * erfc(-(vin - mu) / (sigma * np.sqrt(2)))


def fit_transfer_curve(sweep) -> dict:
    """
    Fit P(1) vs Vin to a Gaussian CDF to extract:
      mu    — input offset voltage (CDF midpoint)
      sigma — input-referred noise RMS

    Parameters
    ----------
    sweep : list of dicts with keys {vin_mv, p1}

    Returns
    -------
    dict with keys:
      mu_v, sigma_v      — fitted values in volts
      mu_uv, sigma_uv    — same in µV
      vin_arr            — Vin values used for fit (V)
      p1_arr             — measured P(1) values (0–1)
      p1_fit             — fitted CDF evaluated at vin_arr
      fit_ok             — bool, True if curve_fit converged
      perr               — 1-sigma parameter uncertainties [mu_v, sigma_v]
    """
    vin_arr = np.array([r["vin_mv"] * 1e-3 for r in sweep])
    p1_arr  = np.array([r["p1"]            for r in sweep])

    # Initial guess: mu=0, sigma estimated from slope at p1≈0.5
    # If no points near 50%, fall back to sigma=500uV
    mid_idx = np.argmin(np.abs(p1_arr - 0.5))
    p0_mu   = vin_arr[mid_idx]
    p0_sig  = 500e-6

    fit_ok = False
    popt   = np.array([p0_mu, p0_sig])
    pcov   = np.full((2, 2), np.nan)

    try:
        popt, pcov = curve_fit(
            _gauss_cdf, vin_arr, p1_arr,
            p0=[p0_mu, p0_sig],
            bounds=([-5e-3, 50e-6], [5e-3, 5e-3]),   # mu in ±5mV, sigma in 50uV–5mV
            maxfev=5000,
        )
        fit_ok = True
    except Exception as e:
        print(f"  [fit] WARNING: curve_fit failed: {e}")

    mu_v, sigma_v = popt
    perr = np.sqrt(np.diag(pcov)) if fit_ok else np.array([np.nan, np.nan])
    p1_fit = _gauss_cdf(vin_arr, mu_v, abs(sigma_v))

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


# ─────────────────────────────────────────────────────────────────────────────
# FOM calculation
# ─────────────────────────────────────────────────────────────────────────────
def compute_fom(results) -> dict:
    """
    Compute comparator performance metrics and FOM.

    sigma_uv  : input-referred noise [µV] — from Gaussian CDF fit to sweep data
    mu_uv     : input offset voltage [µV] — CDF midpoint from fit
    p_avg_uw  : average power [µW] — VDD * mean(|i_VDD|) from noise sweep Vin=0
    tcmp_ps   : comparison time [ps] — avg CLK→OUTP crossing over 1000 cycles at Vin=+1mV
    fom1      : sigma_n^2 * P_avg   [nJ·µV²]
    fom2      : sigma_n^2 * P_avg * Tcmp  [nJ·µV²·ns]

    Writes logs/fom_report.txt and returns the metric dict.
    """
    # ── Fit transfer curve to extract sigma and mu ────────────────────────────
    fit = fit_transfer_curve(results["sweep"])
    sigma_uv = fit["sigma_uv"]
    mu_uv    = fit["mu_uv"]

    # ── Power from Vin=0 sweep point (1000 cycles → reliable steady-state avg) ─
    wave = results["wave"]
    p_avg_uw = float("nan")
    vin0 = next((r for r in results["sweep"] if r["vin_mv"] == 0.0), None)
    if vin0 is not None and not np.isnan(vin0.get("p_avg_uw", float("nan"))):
        p_avg_uw = vin0["p_avg_uw"]

    # ── Tcmp from Vin=+1mV sweep point: avg CLK→OUTP crossing over 1000 cycles ─
    tcmp_ps = float("nan")
    vin1 = next((r for r in results["sweep"] if r["vin_mv"] == 1.0), None)
    if vin1 is not None and not np.isnan(vin1.get("tcmp_ps", float("nan"))):
        tcmp_ps = vin1["tcmp_ps"]

    # ── FOM ───────────────────────────────────────────────────────────────────
    # Standard comparator FOM:
    #   E_cycle [nJ] = P_avg [µW] / FCLK [GHz] / 1e6
    #     because 1 µW / 1 GHz = 1 fJ = 1e-6 nJ  ✓
    #   FOM1 [nJ·µV²] = E_cycle [nJ] × sigma_n² [µV²]
    #   FOM2 [nJ·µV²·ns] = FOM1 × Tcmp [ns]
    #
    # Typical values (45nm, 1GHz): FOM1 ~ 8–30 nJ·µV²
    # Example: sigma=500uV, P=100uW, f=1GHz
    #   E_cycle = 100e-6 nJ, FOM1 = 100e-6 × 500² = 25 nJ·µV²
    FCLK_GHZ = FCLK / 1e9
    fom1 = fom2 = float("nan")
    if not any(np.isnan([sigma_uv, p_avg_uw])):
        e_cycle_nj = p_avg_uw / FCLK_GHZ * 1e-6    # nJ  (1 µW/GHz = 1 fJ = 1e-6 nJ)
        fom1 = e_cycle_nj * (sigma_uv ** 2)          # nJ·µV²
    if not any(np.isnan([fom1, tcmp_ps])):
        fom2 = fom1 * (tcmp_ps / 1e3)               # nJ·µV²·ns

    # ── Write log ─────────────────────────────────────────────────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "fom_report.txt"
    p = results["params"]

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  StrongArm Comparator -- Performance Report\n")
        f.write("=" * 60 + "\n\n")

        f.write("Circuit parameters\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Technology   : {p['L_NM']}nm PTM HP\n")
        f.write(f"  VDD          : {p['VDD']:.2f} V\n")
        f.write(f"  VCM          : {p['VCM']:.2f} V\n")
        f.write(f"  FCLK         : {p['FCLK']/1e9:.1f} GHz\n")
        f.write(f"  Noise BW     : {p['NOISE_BW_GHZ']:.0f} GHz (trnoise BW)\n")
        f.write(f"  Noise NA     : {p['NOISE_NA_UV']:.0f} uV per side (injected amplitude)\n")
        for dev, wval in p["W"].items():
            f.write(f"  W_{dev:<6}     : {wval:.1f} um\n")
        f.write("\n")

        f.write("Transfer curve sweep (P(1) vs Vin)\n")
        f.write("-" * 40 + "\n")
        f.write(f"  {'Vin (mV)':>10}  {'count_1':>8}  {'count_0':>8}  {'P(1) (%)':>10}\n")
        for r in results["sweep"]:
            f.write(f"  {r['vin_mv']:>10.2f}  {r['count_1']:>8d}  "
                    f"{r['count_0']:>8d}  {r['p1']*100:>10.1f}\n")
        f.write("\n")

        f.write("Gaussian CDF fit  [P(1) = Phi((Vin - mu) / sigma)]\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Fit converged: {'Yes' if fit['fit_ok'] else 'No'}\n")
        f.write(f"  Noise sigma  : {sigma_uv:.1f} uV  "
                f"(+/- {fit['perr'][1]*1e6:.1f} uV)\n")
        f.write(f"  Offset mu    : {mu_uv:.1f} uV  "
                f"(+/- {fit['perr'][0]*1e6:.1f} uV)\n")
        f.write("\n")

        f.write("Performance metrics\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Avg power    : {p_avg_uw:.2f} uW   "
                f"(VDD x mean|i_VDD|, noise sweep Vin=0, 1000 cycles)\n")
        f.write(f"  Tcmp         : {tcmp_ps:.1f} ps  "
                f"(avg CLK->OUTP, Vin=+1mV, {SWEEP_NCYC} cycles)\n")
        f.write("\n")

        f.write("Figure of Merit\n")
        f.write("-" * 40 + "\n")
        f.write(f"  FOM1 = E_cycle x sigma_n^2       : {fom1:.4g} nJ*uV^2\n")
        f.write(f"       = (P_avg/FCLK) x sigma_uv^2  [nJ*uV^2]\n")
        f.write(f"  FOM2 = FOM1 x Tcmp               : {fom2:.4g} nJ*uV^2*ns\n")
        f.write("\n")
        f.write("  Reference (45nm, 1GHz): FOM1 ~ 8-30 nJ*uV^2\n")
        f.write(f"\nReport: {log_path}\n")

    print(f"\n  FOM report -> {log_path}")
    return dict(
        sigma_uv = sigma_uv,
        mu_uv    = mu_uv,
        p_avg_uw = p_avg_uw,
        tcmp_ps  = tcmp_ps,
        fom1     = fom1,
        fom2     = fom2,
        fit      = fit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def simulate_all():
    """
    Run all simulations in parallel (waveform + 9-point sweep + ramp).

    Returns
    -------
    dict with keys 'wave', 'sweep', 'ramp', 'params'
    """
    print("\n=== StrongArm Comparator Simulation (45nm, 1GHz) ===")
    print(f"  Noise injection: NA = {NOISE_NA*1e6:.0f} uV per side  "
          f"(BW = {NOISE_BW/1e9:.0f} GHz, nt = {NOISE_NT*1e12:.0f} ps)")
    print(f"  VDD={VDD}V  VCM={VCM}V  W_in={W['inp']}um  W_tail={W['tail']}um")
    print(f"  Sweep: {len(SWEEP_VIN_MV)} Vin levels, {SWEEP_NCYC} cycles each  "
          f"| Ramp: {RAMP_NCYC} cycles\n")
    print(f"  NOTE: sigma_n and mu will be extracted by fitting P(1) vs Vin.\n")

    # Render DUT subcircuit once; all testbenches share the same temp file
    dut_include, dut_tmp = _render_dut()
    print(f"  DUT: comparator_strongarm (L={L_NM}nm, temp: {dut_tmp})")

    tasks = (
        [("wave", lambda: _run_wave(+1.0, dut_include))]
        + [(f"sw_{v:+.2f}", lambda v=v: _run_sweep_point(v, dut_include))
           for v in SWEEP_VIN_MV]
        + [("ramp", lambda: _run_ramp(dut_include))]
    )

    t_total = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {name: pool.submit(fn) for name, fn in tasks}
            results = {name: f.result() for name, f in futures.items()}
    finally:
        os.unlink(dut_tmp)

    wall = time.perf_counter() - t_total
    print(f"\n  Total wall time: {wall:.1f}s ({len(tasks)} sims in parallel)")

    sweep_sorted = sorted(
        [results[f"sw_{v:+.2f}"] for v in SWEEP_VIN_MV],
        key=lambda r: r["vin_mv"],
    )

    return {
        "wave":  results["wave"],
        "sweep": sweep_sorted,
        "ramp":  results["ramp"],
        "params": {
            "VDD": VDD, "VCM": VCM, "FCLK": FCLK,
            "NOISE_BW_GHZ": NOISE_BW / 1e9,
            "NOISE_NA_UV":  NOISE_NA * 1e6,
            "SWEEP_NCYC":   SWEEP_NCYC,
            "RAMP_NCYC":    RAMP_NCYC,
            "L_NM": L_NM, "W": W,
        },
    }
