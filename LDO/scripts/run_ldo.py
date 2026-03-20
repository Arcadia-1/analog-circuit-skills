#!/usr/bin/env python3
"""
run_ldo.py
==========
Master entry point: runs DC, AC, Noise, and Transient simulations in parallel,
then prints a consolidated performance summary.

Usage
-----
  cd LDO/scripts/
  python run_ldo.py

Outputs
-------
  WORK/plots/ldo_dc.png
  WORK/plots/ldo_ac.png
  WORK/plots/ldo_noise.png
  WORK/plots/ldo_tran.png
  WORK/logs/ldo_report.txt
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from simulate_ldo_dc    import simulate_dc
from simulate_ldo_ac    import simulate_ac
from simulate_ldo_noise import simulate_noise
from simulate_ldo_tran  import simulate_tran
from plot_ldo_dc        import plot_dc
from plot_ldo_ac        import plot_ac
from plot_ldo_noise     import plot_noise
from plot_ldo_tran      import plot_tran
from ngspice_common     import LOG_DIR


def _print_report(dc, ac, noise, tran):
    """Print and save a consolidated metrics summary."""
    p      = dc.get("params", {})
    dc_m   = dc.get("op", {})
    ac_m   = ac.get("metrics", {})
    n_m    = noise.get("metrics", {})
    tr_m   = tran.get("metrics", {})

    nan = float("nan")

    vout_v   = dc_m.get("vout", nan)
    line_reg = None
    # Re-derive line reg from sweep arrays
    lr = dc.get("line_reg", {})
    if lr.get("vin_arr") is not None and lr.get("vout_arr") is not None:
        import numpy as np
        vin_a  = lr["vin_arr"]
        vout_a = lr["vout_arr"]
        from simulate_ldo_dc import VIN_REG_MIN
        mask = vin_a >= VIN_REG_MIN
        if mask.sum() > 1:
            line_reg = (float(vout_a[mask][-1]) - float(vout_a[mask][0])) / \
                       (float(vin_a[mask][-1])  - float(vin_a[mask][0]))  * 1e3  # mV/V

    gbw    = ac_m.get("gbw_hz",           nan)
    pm     = ac_m.get("phase_margin_deg", nan)
    dc_lg  = ac_m.get("dc_gain_db",       nan)
    psrr   = ac_m.get("psrr_dc_db",       nan)

    vn_1k  = n_m.get("vn_1k_nvrtHz",     nan)
    vn_rms = n_m.get("vn_rms_uv",        nan)
    corner = n_m.get("flicker_corner_hz", nan)

    v_drop   = tr_m.get("v_drop_mv",         nan)
    ld_tran  = tr_m.get("load_reg_tran_mv",  nan)
    v_over   = tr_m.get("v_overshoot_mv",    nan)
    t_rec    = tr_m.get("t_rec_us",          nan)

    def _fmt(val, fmt, unit):
        if val != val:   # NaN
            return "N/A"
        return f"{val:{fmt}} {unit}"

    lines = [
        "=" * 60,
        "  LDO Performance Summary — PTM 180nm",
        "=" * 60,
        f"  Technology : PTM 180nm BSIM3v3 (NMOS / PMOS)",
        f"  VIN_NOM    : {p.get('VIN_NOM','?')} V",
        f"  VOUT_NOM   : {p.get('VOUT_NOM','?')} V",
        f"  VREF_NOM   : {p.get('VREF_NOM','?')} V",
        f"  R_COMP     : {p.get('R_COMP','?')} Ω",
        f"  C_COMP     : {p.get('C_COMP', nan)*1e12:.0f} pF",
        f"  C_OUT      : {p.get('C_OUT', nan)*1e6:.1f} uF",
        "-" * 60,
        "  DC",
        f"    VOUT @ nom      : {_fmt(vout_v*1e3 if vout_v==vout_v else nan, '.2f', 'mV')}",
        f"    Line regulation : {_fmt(line_reg, '.2f', 'mV/V') if line_reg is not None else 'N/A'}",
        "-" * 60,
        "  AC",
        f"    DC loop gain    : {_fmt(dc_lg,  '.1f', 'dB')}",
        f"    GBW             : {_fmt(gbw/1e3 if gbw==gbw else nan, '.1f', 'kHz')}",
        f"    Phase margin    : {_fmt(pm,     '.1f', '°')}",
        f"    PSRR @ DC       : {_fmt(psrr,   '.1f', 'dB')}",
        "-" * 60,
        "  Noise",
        f"    Vn @ 1 kHz      : {_fmt(vn_1k,  '.1f', 'nV/rtHz')}",
        f"    Vn_rms (10Hz-100kHz): {_fmt(vn_rms, '.2f', 'uV_rms')}",
        f"    1/f corner      : {_fmt(corner/1e3 if corner==corner else nan, '.1f', 'kHz')}",
        "-" * 60,
        "  Transient (0→100 mA load step)",
        f"    VOUT undershoot : {_fmt(v_drop,  '.1f', 'mV')}",
        f"    VOUT overshoot  : {_fmt(v_over,  '.1f', 'mV')}",
        f"    ΔVout static    : {_fmt(ld_tran, '.1f', 'mV')}",
        f"    Recovery (1%)   : {_fmt(t_rec,   '.2f', 'us')}",
        "=" * 60,
    ]

    report = "\n".join(lines)
    print("\n" + report)

    report_path = LOG_DIR / "ldo_report.txt"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report + "\n", encoding="utf-8")
    print(f"\n  Report -> {report_path.name}")


def main():
    t0 = time.perf_counter()
    print("=== LDO Master Simulation (DC + AC + Noise + Tran in parallel) ===")

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_dc    = pool.submit(simulate_dc)
        fut_ac    = pool.submit(simulate_ac)
        fut_noise = pool.submit(simulate_noise)
        fut_tran  = pool.submit(simulate_tran)
        results   = {}
        for fut in as_completed([fut_dc, fut_ac, fut_noise, fut_tran]):
            if fut is fut_dc:
                results["dc"] = fut.result()
            elif fut is fut_ac:
                results["ac"] = fut.result()
            elif fut is fut_noise:
                results["noise"] = fut.result()
            else:
                results["tran"] = fut.result()

    plot_dc   (results["dc"])
    plot_ac   (results["ac"])
    plot_noise(results["noise"])
    plot_tran (results["tran"])

    _print_report(results["dc"], results["ac"],
                  results["noise"], results["tran"])

    elapsed = time.perf_counter() - t0
    print(f"\nAll done in {elapsed:.1f}s")
    print("  Plots  -> WORK/plots/ldo_{{dc,ac,noise,tran}}.png")


if __name__ == "__main__":
    main()
