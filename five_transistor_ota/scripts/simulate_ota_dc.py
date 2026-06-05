#!/usr/bin/env python3
"""DC transfer simulation for the five-transistor OTA."""

import numpy as np

from ngspice_common import LOG_DIR, parse_wrdata, spath
from ota_common import VCM, common_kw, params, render_dut, run_netlist

VSWEEP = 50e-3
VSTEP = 0.25e-3


def simulate_dc():
    print("\n=== Five-Transistor OTA DC Transfer ===")
    dut = render_dut()
    out_vinp = LOG_DIR / "ota_dc_vinp.txt"
    out_vout = LOG_DIR / "ota_dc_vout.txt"
    kw = dict(
        **common_kw(dut),
        vstart=f"{VCM - VSWEEP:.8f}",
        vstop=f"{VCM + VSWEEP:.8f}",
        vstep=f"{VSTEP:.8f}",
        out_vinp=spath(out_vinp),
        out_vout=spath(out_vout),
    )
    rc = run_netlist("testbench_ota_dc.cir.tmpl", kw, "ota_dc.log")
    vinp = parse_wrdata(out_vinp)
    vout = parse_wrdata(out_vout)
    vin = vinp[:, 1] if vinp is not None else None
    out = vout[:, 1] if vout is not None else None

    gain_mid = float("nan")
    vout_mid = float("nan")
    if vin is not None and out is not None and len(vin) > 3:
        dv = vin - VCM
        idx = int(np.argmin(np.abs(dv)))
        vout_mid = float(out[idx])
        lo = max(0, idx - 3)
        hi = min(len(vin), idx + 4)
        slope = np.polyfit(dv[lo:hi], out[lo:hi], 1)[0]
        gain_mid = float(slope)
        print(f"  [dc] Vout@zero-diff = {vout_mid:.4f} V")
        print(f"  [dc] local gain = {gain_mid:.1f} V/V ({20*np.log10(abs(gain_mid)):.1f} dB)")

    return {
        "dc": {"vin": vin, "vout": out, "gain_mid": gain_mid, "vout_mid": vout_mid},
        "rc": rc,
        "params": params({"VSWEEP": VSWEEP, "VSTEP": VSTEP}),
    }


if __name__ == "__main__":
    simulate_dc()

