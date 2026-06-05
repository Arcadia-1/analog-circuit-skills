#!/usr/bin/env python3
"""Run the full two-stage op amp simulation suite."""

from ngspice_common import LOG_DIR, check_ngspice
from plot_opamp import plot_ac, plot_dc_nodes, plot_noise
from simulate_opamp_ac import simulate_ac
from simulate_opamp_dc import simulate_dc
from simulate_opamp_noise import simulate_noise
from simulate_opamp_pz import simulate_pz


def main():
    print("=== Two-Stage Op Amp — Full Simulation Suite ===")
    check_ngspice()

    dc = simulate_dc()
    ac = simulate_ac()
    pz = simulate_pz()
    noise = simulate_noise()

    plot_dc_nodes(dc)
    plot_ac(ac)
    plot_noise(noise)

    nodes = dc["dc"].get("nodes", {})
    m_ac = ac.get("metrics", {})
    m_n = noise.get("metrics", {})
    m_pz = pz.get("pz", {})
    ugb_hz = m_ac.get("ugb_hz", float("nan"))
    nondom_hz = m_pz.get("nondominant_pole_hz", float("nan"))
    rhp_zero_hz = m_pz.get("first_rhp_zero_hz", float("nan"))
    nondom_ratio = nondom_hz / ugb_hz
    rhp_zero_ratio = rhp_zero_hz / ugb_hz
    report = (
        "Two-Stage Op Amp Summary\n"
        "==========================\n"
        f"Vout bias     : {nodes.get('out', float('nan')):.4f} V\n"
        f"Node B bias   : {nodes.get('b', float('nan')):.4f} V\n"
        f"PMOS bias     : {nodes.get('pbias', float('nan')):.4f} V\n"
        f"IDD           : {dc['dc'].get('idd_a', float('nan')) * 1e6:.2f} uA\n"
        f"Power         : {dc['dc'].get('power_w', float('nan')) * 1e6:.2f} uW\n"
        f"DC gain       : {m_ac.get('dc_gain_db', float('nan')):.2f} dB\n"
        f"UGB           : {m_ac.get('ugb_hz', float('nan'))/1e6:.3f} MHz\n"
        f"Phase @ UGB   : {m_ac.get('phase_ugb_deg', float('nan')):.2f} deg\n"
        f"Est. PM       : {m_ac.get('phase_margin_deg', float('nan')):.2f} deg\n"
        f"Dominant pole : {m_pz.get('dominant_pole_hz', float('nan'))/1e3:.3f} kHz\n"
        f"Non-dom pole  : {nondom_hz/1e6:.3f} MHz ({nondom_ratio:.2f} x UGB)\n"
        f"First RHP zero: {rhp_zero_hz/1e6:.3f} MHz ({rhp_zero_ratio:.2f} x UGB)\n"
        f"Open-loop output Vn @ 1 kHz : {m_n.get('vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz\n"
        f"Open-loop output Vn rms     : {m_n.get('vn_rms_uv', float('nan')):.2f} uV_rms\n"
        f"Input-referred en @ 1 kHz   : {m_n.get('en_1k_nvrtHz', float('nan')):.2f} nV/rtHz\n"
        f"Unity CL output Vn @ 1 kHz  : {m_n.get('cl_vn_1k_nvrtHz', float('nan')):.2f} nV/rtHz\n"
        f"Unity CL output Vn rms      : {m_n.get('cl_vn_rms_uv', float('nan')):.2f} uV_rms\n"
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "opamp_report.txt"
    path.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"  Report -> {path}")


if __name__ == "__main__":
    main()
