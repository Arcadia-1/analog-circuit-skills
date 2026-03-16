#!/usr/bin/env python3
"""
bootstrap_common.py
===================
Shared circuit parameters, DUT rendering, and helpers for bootstrap switch skill.

Reuses ngspice_common.py from the installed ngspice skill for:
  - Path management (LOG_DIR, PLOT_DIR, MODEL_DIR, NETLIST_DIR)
  - ngspice runner (run_ngspice, find_ngspice)
  - Parsers (parse_wrdata, parse_print_table)
  - Template renderer (render_template)
  - Path helper (spath)
"""

import os
import sys
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Path setup: import ngspice_common from the installed ngspice skill
# ─────────────────────────────────────────────────────────────────────────────
_ASSETS_DIR = Path(__file__).resolve().parent
_REPO_ROOT  = _ASSETS_DIR.parent.parent

# Look for ngspice skill in project-level .claude/skills/
_NGSPICE_SKILL = _REPO_ROOT / ".claude" / "skills" / "ngspice" / "assets"
if not _NGSPICE_SKILL.exists():
    # Fallback: user-level skills
    _NGSPICE_SKILL = Path.home() / ".claude" / "skills" / "ngspice" / "assets"

sys.path.insert(0, str(_NGSPICE_SKILL))
from ngspice_common import (
    run_ngspice, find_ngspice, check_ngspice,
    parse_wrdata, parse_print_table,
    spath, strip_ansi,
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths — local to this skill, outputs to .work_bootstrap/
# ─────────────────────────────────────────────────────────────────────────────
NETLIST_DIR = _ASSETS_DIR / "netlist"
MODEL_DIR   = _NGSPICE_SKILL / "models"   # reuse models from ngspice skill

_WORK_ROOT = Path(os.environ.get("ANALOG_WORK_DIR", str(_REPO_ROOT / ".work_bootstrap")))
LOG_DIR          = _WORK_ROOT / "logs"
PLOT_DIR         = _WORK_ROOT / "plots"
NETLIST_SAVE_DIR = _WORK_ROOT / "netlists"

for _d in (LOG_DIR, PLOT_DIR, NETLIST_SAVE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

MODEL_PATH = spath(MODEL_DIR / "ptm180.lib")

# ─────────────────────────────────────────────────────────────────────────────
# Circuit / technology parameters — 180nm PTM, VDD=1.8V
# ─────────────────────────────────────────────────────────────────────────────
VDD  = 1.8       # V  (180nm nominal supply)
L_NM = 180       # nm

# Clock: 50 MHz (T=20ns) — slow enough for bootstrap to settle
FCLK = 50e6      # Hz
TCLK = 1 / FCLK  # s  = 20 ns

# Transistor widths (µm)
W = dict(
    sw    = 10.0,  # sampling switch MS — wider = lower Ron
    m1    = 3.0,   # PMOS reset (charges CB top)
    m2    = 1.0,   # NMOS reset (discharges CB bottom)
    m3    = 1.0,   # NMOS VIN→CB bottom
    m4    = 3.0,   # PMOS top-plate conduction
    m4a   = 1.0,   # NMOS M4 gate driver
    m4b   = 3.0,   # PMOS M4 gate pre-charge
    m4c   = 1.0,   # NMOS startup
    m5    = 1.0,   # NMOS gate pull-down
    m5a   = 1.0,   # NMOS cascode
    inv_p = 3.0,   # inverter PMOS
    inv_n = 1.0,   # inverter NMOS
)

CB = 1e-12   # F  bootstrap capacitor (1 pF)
CS = 400e-15 # F  sampling capacitor (400 fF)


# ─────────────────────────────────────────────────────────────────────────────
# Template renderer (uses local netlist/ directory)
# ─────────────────────────────────────────────────────────────────────────────
def render_template(tmpl_name, **kw):
    """Read a .cir.tmpl from netlist/ and fill placeholders via str.format()."""
    tmpl_path = NETLIST_DIR / tmpl_name
    text = tmpl_path.read_text(encoding="utf-8")
    return text.format(**kw)


# ─────────────────────────────────────────────────────────────────────────────
# DUT rendering
# ─────────────────────────────────────────────────────────────────────────────
def render_dut(l_nm=None, tag=None):
    """
    Render bootstrap_switch.cir.tmpl → netlists/bootstrap_switch_dut[_tag].cir.

    Parameters
    ----------
    l_nm : int or None
        Channel length in nm. Defaults to L_NM (180nm).
    tag : str or None
        Optional suffix for the output filename, e.g. "45nm" → dut_45nm.cir.
        Use this when running multiple nodes in parallel to avoid file conflicts.

    Returns (include_line_str, None).
    """
    l_nm = l_nm or L_NM
    fname = f"bootstrap_switch_dut{'_' + tag if tag else ''}.cir"
    text = render_template(
        "bootstrap_switch.cir.tmpl",
        L       = f"{l_nm}n",
        W_sw    = W["sw"],
        W_m1    = W["m1"],
        W_m2    = W["m2"],
        W_m3    = W["m3"],
        W_m4    = W["m4"],
        W_m4a   = W["m4a"],
        W_m4b   = W["m4b"],
        W_m4c   = W["m4c"],
        W_m5    = W["m5"],
        W_m5a   = W["m5a"],
        W_inv_p = W["inv_p"],
        W_inv_n = W["inv_n"],
        CB      = f"{CB:.4e}",
    )
    dut_path = NETLIST_SAVE_DIR / fname
    dut_path.write_text(text, encoding="utf-8")
    return f".include {spath(dut_path)}", None


def common_kw(dut_include):
    """Keyword args shared by all testbench templates."""
    return dict(
        VDD        = VDD,
        model_path = MODEL_PATH,
        dut_include = dut_include,
        L          = f"{L_NM}n",
        W_sw       = W["sw"],
        CS         = f"{CS:.4e}",
        fclk_mhz   = FCLK / 1e6,
        tclk       = f"{TCLK:.4e}",
        t_high     = f"{TCLK/2:.4e}",
    )


def run_netlist(tmpl_name, kw, log_path, timeout=120):
    """Render template, write temp file, run ngspice, return exit code."""
    text = render_template(tmpl_name, **kw)
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


def circuit_params(extra=None):
    """Return base circuit parameter dict."""
    p = dict(VDD=VDD, L_NM=L_NM, FCLK=FCLK, CB=CB, CS=CS, W=W)
    if extra:
        p.update(extra)
    return p
