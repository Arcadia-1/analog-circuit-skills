#!/usr/bin/env python3
"""
simulate_ldo_ac.py
==================
AC simulations: PSRR, output impedance Zout, and loop gain.

Public API
----------
simulate_ac() -> dict
    'psrr'      : {freq, mag_db, phase_deg}   PSRR = -mag_db  (positive = rejection)
    'zout'      : {freq, mag_db, phase_deg}   output impedance magnitude
    'loopgain'  : {freq, mag_db, phase_deg}   loop gain T(jω) from flat netlist
    'metrics'   : {gbw_hz, phase_margin_deg, dc_gain_db, psrr_dc_db}
    'params'    : circuit/sim parameters
"""

import time
import numpy as np

import ldo_common as _ldo
from ngspice_common import LOG_DIR, parse_wrdata, spath
from ldo_common import (
    VIN_NOM, VREF_NOM, MODEL_PATH, R_LOAD_DEFAULT,
    circuit_params, render_dut, run_netlist, _mos_params, _fmt_L,
)

# ── AC sweep parameters ───────────────────────────────────────────────────────
AC_PTS  = 100          # points per decade
FSTART  = 1.0          # Hz
FSTOP   = 1e9          # Hz  (1 GHz)


def simulate_ac() -> dict:
    """Run PSRR/Zout (subcircuit TB) and loop gain (flat TB)."""
    print("\n=== LDO AC Simulations ===")
    dut_include, _ = render_dut()

    psrr_zout = _run_psrr_zout(dut_include)
    loopgain  = _run_loopgain()

    metrics = _extract_metrics(loopgain, psrr_zout)

    return {
        "psrr":     psrr_zout["psrr"],
        "zout":     psrr_zout["zout"],
        "loopgain": loopgain,
        "metrics":  metrics,
        "params":   circuit_params({"AC_PTS": AC_PTS, "FSTART": FSTART, "FSTOP": FSTOP}),
    }


# ─────────────────────────────────────────────────────────────────────────────
def _run_psrr_zout(dut_include):
    tag = "ldo_ac_psrr"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log = LOG_DIR / f"{tag}.log"
    paths = {
        "psrr_freq":  LOG_DIR / f"{tag}_psrr_freq.txt",
        "psrr_mag":   LOG_DIR / f"{tag}_psrr_mag.txt",
        "psrr_phase": LOG_DIR / f"{tag}_psrr_phase.txt",
        "zout_freq":  LOG_DIR / f"{tag}_zout_freq.txt",
        "zout_mag":   LOG_DIR / f"{tag}_zout_mag.txt",
        "zout_phase": LOG_DIR / f"{tag}_zout_phase.txt",
    }

    kw = dict(
        vin_dc      = VIN_NOM,
        vref_dc     = VREF_NOM,
        r_load      = R_LOAD_DEFAULT,
        ac_pts      = AC_PTS,
        fstart      = f"{FSTART:.6g}",
        fstop       = f"{FSTOP:.6g}",
        dut_include = dut_include,
        model_path  = MODEL_PATH,
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_ldo_ac_psrr.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load2(freq_key, mag_key, phase_key):
        fd = parse_wrdata(paths[freq_key])
        md = parse_wrdata(paths[mag_key])
        pd = parse_wrdata(paths[phase_key])
        freq  = fd[:, 1] if fd is not None else None
        mag   = md[:, 1] if md is not None else None
        phase = pd[:, 1] if pd is not None else None
        return {"freq": freq, "mag_db": mag, "phase_deg": phase}

    return {
        "psrr": _load2("psrr_freq", "psrr_mag", "psrr_phase"),
        "zout": _load2("zout_freq", "zout_mag", "zout_phase"),
    }


# ─────────────────────────────────────────────────────────────────────────────
def _run_loopgain():
    tag = "ldo_ac_loopgain"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    log = LOG_DIR / f"{tag}.log"
    paths = {
        "lg_freq":  LOG_DIR / f"{tag}_freq.txt",
        "lg_mag":   LOG_DIR / f"{tag}_mag.txt",
        "lg_phase": LOG_DIR / f"{tag}_phase.txt",
    }

    def _mp(W_um, L_nm):
        return _mos_params(W_um, L_nm)

    ad_m6, as_m6, pd_m6, ps_m6, nrd_m6, nrs_m6 = _mp(_ldo.W_M6_UM, _ldo.L_M6_NM)
    ad_m5, as_m5, pd_m5, ps_m5, nrd_m5, nrs_m5 = _mp(_ldo.W_M5_UM, _ldo.L_M5_NM)
    ad_m0, as_m0, pd_m0, ps_m0, nrd_m0, nrs_m0 = _mp(_ldo.W_M0_UM, _ldo.L_M0_NM)
    ad_m1, as_m1, pd_m1, ps_m1, nrd_m1, nrs_m1 = _mp(_ldo.W_M1_UM, _ldo.L_M1_NM)
    ad_m3, as_m3, pd_m3, ps_m3, nrd_m3, nrs_m3 = _mp(_ldo.W_M3_UM, _ldo.L_M3_NM)
    ad_m4, as_m4, pd_m4, ps_m4, nrd_m4, nrs_m4 = _mp(_ldo.W_M4_UM, _ldo.L_M4_NM)
    ad_m2, as_m2, pd_m2, ps_m2, nrd_m2, nrs_m2 = _mp(_ldo.W_M2_UM, _ldo.L_M2_NM)

    kw = dict(
        vin_dc     = VIN_NOM,
        vref_dc    = VREF_NOM,
        r_load     = R_LOAD_DEFAULT,
        ibias_ua   = _ldo.IBIAS_UA,
        c_ibias    = f"{_ldo.C_IBIAS:.6g}",
        r_comp     = _ldo.R_COMP,
        c_comp     = f"{_ldo.C_COMP:.6e}",
        c_out      = f"{_ldo.C_OUT:.6e}",
        r_fb_top   = _ldo.R_FB_TOP,
        r_fb_bot   = _ldo.R_FB_BOT,
        ac_pts     = AC_PTS,
        fstart     = f"{FSTART:.6g}",
        fstop      = f"{FSTOP:.6g}",
        model_path = MODEL_PATH,
        # M6
        w_m6=f"{_ldo.W_M6_UM}u", l_m6=_fmt_L(_ldo.L_M6_NM), m_m6=_ldo.M_M6,
        ad_m6=ad_m6, as_m6=as_m6, pd_m6=pd_m6, ps_m6=ps_m6, nrd_m6=nrd_m6, nrs_m6=nrs_m6,
        # M5
        w_m5=f"{_ldo.W_M5_UM}u", l_m5=_fmt_L(_ldo.L_M5_NM), m_m5=_ldo.M_M5,
        ad_m5=ad_m5, as_m5=as_m5, pd_m5=pd_m5, ps_m5=ps_m5, nrd_m5=nrd_m5, nrs_m5=nrs_m5,
        # M0
        w_m0=f"{_ldo.W_M0_UM}u", l_m0=_fmt_L(_ldo.L_M0_NM), m_m0=_ldo.M_M0,
        ad_m0=ad_m0, as_m0=as_m0, pd_m0=pd_m0, ps_m0=ps_m0, nrd_m0=nrd_m0, nrs_m0=nrs_m0,
        # M1
        w_m1=f"{_ldo.W_M1_UM}u", l_m1=_fmt_L(_ldo.L_M1_NM), m_m1=_ldo.M_M1,
        ad_m1=ad_m1, as_m1=as_m1, pd_m1=pd_m1, ps_m1=ps_m1, nrd_m1=nrd_m1, nrs_m1=nrs_m1,
        # M3
        w_m3=f"{_ldo.W_M3_UM}u", l_m3=_fmt_L(_ldo.L_M3_NM), m_m3=_ldo.M_M3,
        ad_m3=ad_m3, as_m3=as_m3, pd_m3=pd_m3, ps_m3=ps_m3, nrd_m3=nrd_m3, nrs_m3=nrs_m3,
        # M4
        w_m4=f"{_ldo.W_M4_UM}u", l_m4=_fmt_L(_ldo.L_M4_NM), m_m4=_ldo.M_M4,
        ad_m4=ad_m4, as_m4=as_m4, pd_m4=pd_m4, ps_m4=ps_m4, nrd_m4=nrd_m4, nrs_m4=nrs_m4,
        # M2
        w_m2=f"{_ldo.W_M2_UM}u", l_m2=_fmt_L(_ldo.L_M2_NM), m_m2=_ldo.M_M2,
        ad_m2=ad_m2, as_m2=as_m2, pd_m2=pd_m2, ps_m2=ps_m2, nrd_m2=nrd_m2, nrs_m2=nrs_m2,
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    rc = run_netlist("testbench_ldo_ac_loopgain.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    fd = parse_wrdata(paths["lg_freq"])
    md = parse_wrdata(paths["lg_mag"])
    pd = parse_wrdata(paths["lg_phase"])

    freq     = fd[:, 1] if fd is not None else None
    mag_raw  = md[:, 1] if md is not None else None   # vdb(net30), dB
    phase_raw = pd[:, 1] if pd is not None else None  # vp(net30),  radians

    T_mag_db = T_phase_deg = None
    if mag_raw is not None and phase_raw is not None:
        # Reconstruct complex V(net30) from vdb + vp (vp is in radians in ngspice 45.x)
        V_net30 = 10 ** (mag_raw / 20) * np.exp(1j * phase_raw)
        # Vtest = 1V AC, so V(net2) = V(net30) + 1
        V_net2  = V_net30 + 1.0
        # True loop gain: T = -V(net30) / V(net2)
        T = -V_net30 / V_net2
        T_mag_db    = 20 * np.log10(np.abs(T))
        # Unwrap phase for continuous display (no discontinuous jumps above GBW)
        T_phase_deg = np.degrees(np.unwrap(np.angle(T)))  # ~0° at DC, decreases continuously
        # Truncate at the minimum of T_mag after GBW to remove injection-method artifacts.
        # After the true 0-dB crossing, T_mag should only decrease; any subsequent rise
        # is caused by C_ibias=1F shorting net16→VSS via M1 Cgs, not a real zero.
        # Find the first 0-dB crossing (GBW index) then locate minimum T_mag after it.
        gbw_idx = None
        for i in range(len(T_mag_db) - 1):
            if (T_mag_db[i]) * (T_mag_db[i + 1]) <= 0 and T_mag_db[i] > 0:
                gbw_idx = i + 1
                break
        if gbw_idx is not None:
            post_gbw = T_mag_db[gbw_idx:]
            min_idx  = int(np.argmin(post_gbw)) + gbw_idx
            T_mag_db[min_idx + 1:]    = np.nan
            T_phase_deg[min_idx + 1:] = np.nan

    return {"freq": freq, "mag_db": T_mag_db, "phase_deg": T_phase_deg, "rc": rc}


# ─────────────────────────────────────────────────────────────────────────────
def _extract_metrics(loopgain, psrr_zout):
    metrics = {}

    lg_freq = loopgain.get("freq")
    lg_mag  = loopgain.get("mag_db")
    lg_ph   = loopgain.get("phase_deg")

    if lg_freq is not None and lg_mag is not None:
        # DC loop gain: first point (lowest frequency), T decreases with freq
        metrics["dc_gain_db"] = float(lg_mag[0])

        # GBW: frequency where T_mag_db crosses 0 dB (from positive to negative)
        # Only search in the valid (non-NaN) region
        gbw_hz = float("nan")
        for i in range(len(lg_mag) - 1):
            if np.isnan(lg_mag[i]) or np.isnan(lg_mag[i + 1]):
                continue
            if (lg_mag[i] - 0) * (lg_mag[i + 1] - 0) <= 0:
                frac = (0 - lg_mag[i]) / (lg_mag[i + 1] - lg_mag[i])
                gbw_hz = float(10 ** (
                    np.log10(lg_freq[i]) + frac * (np.log10(lg_freq[i+1]) - np.log10(lg_freq[i]))
                ))
                break
        metrics["gbw_hz"] = gbw_hz

        # Phase margin: 180° + angle(T) at GBW  (T_phase_deg is in degrees, ~0° at DC)
        if not np.isnan(gbw_hz) and lg_ph is not None:
            ph_at_gbw = float(np.interp(np.log10(gbw_hz),
                                        np.log10(lg_freq), lg_ph))
            metrics["phase_margin_deg"] = 180.0 + ph_at_gbw
        else:
            metrics["phase_margin_deg"] = float("nan")

        if not np.isnan(gbw_hz):
            print(f"  [loop_gain] GBW = {gbw_hz/1e3:.1f} kHz, "
                  f"PM = {metrics['phase_margin_deg']:.1f}°", flush=True)

    # PSRR at DC (first frequency point)
    psrr_freq = psrr_zout["psrr"].get("freq")
    psrr_mag  = psrr_zout["psrr"].get("mag_db")
    if psrr_mag is not None:
        metrics["psrr_dc_db"] = float(-psrr_mag[0])
        print(f"  [PSRR] DC PSRR = {metrics['psrr_dc_db']:.1f} dB", flush=True)

    # PSRR spot values at 1 kHz and 100 kHz  (PSRR = -mag_db for rejection in dB)
    # Also extract Vout/Vin magnitude (linear) at those frequencies for mV/V metric
    if psrr_freq is not None and psrr_mag is not None:
        log_f = np.log10(psrr_freq)
        for f_spot, key_db, key_mvv in [
            (1e3,  "psrr_1k_db",  "linereg_1k_mvv"),
            (100e3, "psrr_100k_db", "linereg_100k_mvv"),
        ]:
            if psrr_freq[0] <= f_spot <= psrr_freq[-1]:
                mag_db_val = float(np.interp(np.log10(f_spot), log_f, psrr_mag))
                psrr_db    = -mag_db_val          # positive = rejection
                lin_mvv    = 10 ** (mag_db_val / 20) * 1e3   # |Vout/Vin| in mV/V
                metrics[key_db]  = psrr_db
                metrics[key_mvv] = lin_mvv
                print(f"  [PSRR] @ {f_spot/1e3:.0f} kHz: PSRR={psrr_db:.1f} dB  "
                      f"(line_reg={lin_mvv:.2f} mV/V)", flush=True)

    # Zout spot values at 1 kHz and 100 kHz  (mag_db is 20·log10|Zout| in dBΩ)
    zout_freq = psrr_zout["zout"].get("freq")
    zout_mag  = psrr_zout["zout"].get("mag_db")
    if zout_freq is not None and zout_mag is not None:
        log_fz = np.log10(zout_freq)
        for f_spot, key in [(1e3, "zout_1k_mohm"), (100e3, "zout_100k_mohm")]:
            if zout_freq[0] <= f_spot <= zout_freq[-1]:
                mag_db_val = float(np.interp(np.log10(f_spot), log_fz, zout_mag))
                zout_ohm   = 10 ** (mag_db_val / 20)
                zout_mohm  = zout_ohm * 1e3
                metrics[key] = zout_mohm
                print(f"  [Zout] @ {f_spot/1e3:.0f} kHz: {zout_mohm:.2f} mΩ", flush=True)

    return metrics
