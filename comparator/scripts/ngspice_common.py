#!/usr/bin/env python3
"""
ngspice_common.py
=================
Shared utilities for the ngspice skill.

Provides path constants, ngspice runner, and output parsers used by all
simulation scripts.
"""

import subprocess
import sys
import re
import shutil
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent        # comparator/scripts/
_ASSET_DIR  = BASE_DIR.parent / 'assets'            # comparator/assets/
NETLIST_DIR = _ASSET_DIR / 'netlist'
MODEL_DIR   = _ASSET_DIR / 'models'

# All generated output (logs, plots, cached data) goes to WORK/ at the repo
# root so the skill package stays clean.  The env-var ANALOG_WORK_DIR can
# override this location if needed.
import os as _os
_REPO_ROOT = BASE_DIR.parent.parent                  # .../analog-circuit-skills/
_WORK_ROOT = Path(_os.environ.get("ANALOG_WORK_DIR",
                                   str(_REPO_ROOT / "WORK")))
LOG_DIR  = _WORK_ROOT / "logs"
PLOT_DIR = _WORK_ROOT / "plots"
NETLIST_SAVE_DIR = _WORK_ROOT / "netlists"
NETLIST_DUT_DIR  = NETLIST_SAVE_DIR / "dut"
NETLIST_TB_DIR   = NETLIST_SAVE_DIR / "testbench"
for _d in (LOG_DIR, PLOT_DIR, NETLIST_DUT_DIR, NETLIST_TB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def strip_ansi(text):
    """Remove ANSI escape codes from terminal output."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def spath(p):
    """Convert a Path to a string with forward slashes (for SPICE netlists)."""
    return str(p).replace('\\', '/')


def find_ngspice():
    """Return the ngspice executable path (prefer ngspice_con on Windows)."""
    if shutil.which("ngspice_con"):
        return "ngspice_con"
    if shutil.which("ngspice"):
        return "ngspice"
    # Fallback: check known Windows install location
    for candidate in [
        r"C:\Program Files\Spice64\bin\ngspice_con.exe",
        r"C:\Program Files\Spice64\bin\ngspice.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return "ngspice"  # let subprocess raise a clear error if still not found


# ─────────────────────────────────────────────────────────────────────────────
# Template renderer
# ─────────────────────────────────────────────────────────────────────────────
def render_template(tmpl_name, **kw):
    """Read a .cir.tmpl from netlist/ and fill placeholders via str.format()."""
    tmpl_path = NETLIST_DIR / tmpl_name
    text = tmpl_path.read_text(encoding='utf-8')
    return text.format(**kw)


# ─────────────────────────────────────────────────────────────────────────────
# ngspice runner
# ─────────────────────────────────────────────────────────────────────────────
def run_ngspice(netlist, log=None, timeout=120):
    """
    Run ngspice in batch mode.

    Parameters
    ----------
    netlist : str or Path
        Path to the netlist file.
    log : str or Path, optional
        Path for the simulation log file.
    timeout : int
        Subprocess timeout in seconds.

    Returns
    -------
    int
        ngspice exit code.
    """
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
def parse_print_table(log_path):
    """
    Parse ngspice .print tabular output → ndarray (N, n_cols).

    The format is tab-separated: index \\t val1 \\t val2 ...
    """
    rows = {}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and re.match(r"^\d+$", parts[0]):
                try:
                    idx = int(parts[0])
                    vals = [float(p.rstrip(',')) for p in parts[1:]
                           if p.strip() and p.strip(',')]
                    if vals:
                        rows[idx] = vals
                except ValueError:
                    pass
    return np.array([rows[k] for k in sorted(rows)]) if rows else None


def parse_wrdata(data_path):
    """
    Parse ngspice wrdata output → ndarray (N, 2).

    Format: freq_or_time  value  (whitespace-separated, two columns).
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
