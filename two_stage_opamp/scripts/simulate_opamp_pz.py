#!/usr/bin/env python3
"""Pole-zero simulation for the two-stage op amp."""

import math
import re

from ngspice_common import LOG_DIR
from opamp_common import common_kw, params, render_dut, run_netlist

NUM_RE = r"([+-]?\d+(?:\.\d+)?e[+-]?\d+)"
POLE_RE = re.compile(rf"pole\((\d+)\)\s*=\s*{NUM_RE},\s*{NUM_RE}")
ZERO_RE = re.compile(rf"zero\((\d+)\)\s*=\s*{NUM_RE},\s*{NUM_RE}")


def _parse_points(text, regex):
    points = []
    for match in regex.finditer(text):
        idx = int(match.group(1))
        real = float(match.group(2))
        imag = float(match.group(3))
        if abs(real) < 1e-9 and abs(imag) < 1e-9:
            continue
        points.append({"idx": idx, "real": real, "imag": imag, "hz": math.hypot(real, imag) / (2 * math.pi)})
    return sorted(points, key=lambda p: p["hz"])


def simulate_pz():
    print("\n=== Two-Stage Op Amp Pole-Zero Analysis ===")
    dut = render_dut()
    kw = common_kw(dut)
    log_path = LOG_DIR / "opamp_pz.log"
    rc = run_netlist("testbench_opamp_pz.cir.tmpl", kw, "opamp_pz.log")
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    poles = _parse_points(text, POLE_RE)
    zeros = _parse_points(text, ZERO_RE)

    dominant = poles[0] if poles else None
    nondom = poles[1] if len(poles) > 1 else None
    rhp_zeros = [z for z in zeros if z["real"] > 0]
    lhp_zeros = [z for z in zeros if z["real"] < 0]
    first_rhp_zero = rhp_zeros[0] if rhp_zeros else None

    if dominant:
        print(f"  [pz] dominant pole = {dominant['hz']/1e3:.2f} kHz")
    if nondom:
        print(f"  [pz] first non-dominant pole = {nondom['hz']/1e6:.2f} MHz")
    if first_rhp_zero:
        print(f"  [pz] first RHP zero = {first_rhp_zero['hz']/1e6:.2f} MHz")
    elif lhp_zeros:
        print(f"  [pz] first LHP zero = {lhp_zeros[0]['hz']/1e6:.2f} MHz")

    return {
        "pz": {
            "poles": poles,
            "zeros": zeros,
            "dominant_pole_hz": dominant["hz"] if dominant else float("nan"),
            "nondominant_pole_hz": nondom["hz"] if nondom else float("nan"),
            "first_rhp_zero_hz": first_rhp_zero["hz"] if first_rhp_zero else float("nan"),
            "first_lhp_zero_hz": lhp_zeros[0]["hz"] if lhp_zeros else float("nan"),
        },
        "rc": rc,
        "params": params(),
    }


if __name__ == "__main__":
    simulate_pz()
