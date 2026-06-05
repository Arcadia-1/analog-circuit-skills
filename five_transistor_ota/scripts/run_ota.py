#!/usr/bin/env python3
"""Run the full five-transistor OTA simulation suite."""

from pathlib import Path

from ngspice_common import LOG_DIR, check_ngspice
from plot_ota import plot_ac, plot_dc, plot_noise
from simulate_ota_ac import simulate_ac
from simulate_ota_dc import simulate_dc
from simulate_ota_noise import simulate_noise


def main():
    print("=== Five-Transistor OTA — Full Simulation Suite ===")
    check_ngspice()

    dc = simulate_dc()
    ac = simulate_ac()
    noise = simulate_noise()

    plot_dc(dc)
    plot_ac(ac)
    plot_noise(noise)

    m_ac = ac.get("metrics", {})
    m_n = noise.get("metrics", {})
    report = (
        "Five-Transistor OTA Summary\n"
        "============================\n"
        f"DC gain       : {m_ac.get('dc_gain_db', float('nan')):.2f} dB\n"
        f"UGB           : {m_ac.get('ugb_hz', float('nan'))/1e6:.3f} MHz\n"
        f"Phase @ UGB   : {m_ac.get('phase_ugb_deg', float('nan')):.2f} deg\n"
        f"Vn @ 1 kHz    : {m_n.get('vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz\n"
        f"Vn rms        : {m_n.get('vn_rms_uv', float('nan')):.2f} uV_rms\n"
        f"DC local gain : {dc['dc'].get('gain_mid', float('nan')):.2f} V/V\n"
        f"Vout bias     : {dc['dc'].get('vout_mid', float('nan')):.4f} V\n"
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "ota_report.txt"
    path.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"  Report -> {path}")


if __name__ == "__main__":
    main()
