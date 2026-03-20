#!/usr/bin/env python3
"""
ngspice_common.py  (LDO)
========================
Shared utilities: paths, ngspice runner, output parsers.
Mirrors comparator/scripts/ngspice_common.py with LDO-specific paths.
"""

import subprocess
import sys
import re
import shutil
import numpy as np
from pathlib import Path
import os as _os

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent        # LDO/scripts/
_ASSET_DIR  = BASE_DIR.parent / 'assets'            # LDO/assets/
NETLIST_DIR = _ASSET_DIR / 'netlist'
MODEL_DIR   = _ASSET_DIR / 'models'                  # LDO/assets/models/

_REPO_ROOT = BASE_DIR.parent.parent                  # analog-circuit-skills/
_WORK_ROOT = Path(_os.environ.get("ANALOG_WORK_DIR",
                                   str(_REPO_ROOT / "WORK")))
LOG_DIR          = _WORK_ROOT / "logs"
PLOT_DIR         = _WORK_ROOT / "plots"
NETLIST_SAVE_DIR = _WORK_ROOT / "netlists"
NETLIST_DUT_DIR  = NETLIST_SAVE_DIR / "dut"
NETLIST_TB_DIR   = NETLIST_SAVE_DIR / "testbench"
for _d in (LOG_DIR, PLOT_DIR, NETLIST_DUT_DIR, NETLIST_TB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def strip_ansi(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def spath(p):
    """Forward-slash path string for SPICE .include directives."""
    return str(p).replace('\\', '/')


def find_ngspice():
    if shutil.which("ngspice_con"):
        return "ngspice_con"
    if shutil.which("ngspice"):
        return "ngspice"
    for candidate in [
        r"C:\Program Files\ngspice-45.2_64\Spice64\bin\ngspice_con.exe",
        r"C:\Program Files\ngspice-45.2_64\Spice64\bin\ngspice.exe",
        r"C:\Program Files\Spice64\bin\ngspice_con.exe",
        r"C:\Program Files\Spice64\bin\ngspice.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return "ngspice"


# ─────────────────────────────────────────────────────────────────────────────
# Template renderer
# ─────────────────────────────────────────────────────────────────────────────
def render_template(tmpl_name, **kw):
    """Read .cir.tmpl from netlist/ and fill placeholders via str.format()."""
    tmpl_path = NETLIST_DIR / tmpl_name
    text = tmpl_path.read_text(encoding='utf-8')
    return text.format(**kw)


# ─────────────────────────────────────────────────────────────────────────────
# ngspice runner
# ─────────────────────────────────────────────────────────────────────────────
def run_ngspice(netlist, log=None, timeout=120):
    exe = find_ngspice()
    args = [exe, "-b"]
    if log:
        args += ["-o", str(log)]
    args.append(str(netlist))
    kwargs = dict(
        args=args,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(**kwargs).returncode


# ─────────────────────────────────────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────────────────────────────────────
def parse_wrdata(data_path):
    """
    Parse ngspice wrdata output → ndarray (N, 2).
    Format: x_value  y_value  (two whitespace-separated columns).
    """
    rows = []
    with open(data_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    rows.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
    return np.array(rows) if rows else None
