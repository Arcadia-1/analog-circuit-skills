#!/usr/bin/env python3
"""DC operating-point simulation for the two-stage op amp."""

from ngspice_common import LOG_DIR, parse_wrdata, spath
from opamp_common import common_kw, params, render_dut, run_netlist


def _last_values(data):
    if data is None or data.size == 0:
        return []
    row = data[-1]
    return [float(x) for x in row[1::2]]


def simulate_dc():
    print("\n=== Two-Stage Op Amp DC Operating Point ===")
    dut = render_dut()
    paths = {
        "nodes": LOG_DIR / "opamp_dc_nodes.txt",
        "currents": LOG_DIR / "opamp_dc_currents.txt",
    }
    kw = dict(
        **common_kw(dut),
        out_nodes=spath(paths["nodes"]),
        out_currents=spath(paths["currents"]),
    )
    rc = run_netlist("testbench_opamp_dc.cir.tmpl", kw, "opamp_dc.log")

    node_names = ["inp", "inn", "c", "a", "b", "out", "pbias"]
    node_values = _last_values(parse_wrdata(paths["nodes"]))
    nodes = dict(zip(node_names, node_values))

    current_values = _last_values(parse_wrdata(paths["currents"]))
    idd_a = -current_values[0] if current_values else float("nan")
    power_w = idd_a * params()["VDD"]

    print(f"  [dc] Vout = {nodes.get('out', float('nan')):.4f} V")
    print(f"  [dc] first-stage node B = {nodes.get('b', float('nan')):.4f} V")
    print(f"  [dc] PMOS bias node = {nodes.get('pbias', float('nan')):.4f} V")
    print(f"  [dc] IDD = {idd_a * 1e6:.2f} uA, Power = {power_w * 1e6:.2f} uW")

    return {
        "dc": {"nodes": nodes, "idd_a": idd_a, "power_w": power_w},
        "rc": rc,
        "params": params(),
    }


if __name__ == "__main__":
    simulate_dc()
