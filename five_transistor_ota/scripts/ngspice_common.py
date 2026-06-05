#!/usr/bin/env python3
"""Shared ngspice helpers for the five_transistor_ota skill."""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
SKILL_DIR = BASE_DIR.parent
ASSET_DIR = SKILL_DIR / "assets"
NETLIST_DIR = ASSET_DIR / "netlist"
MODEL_DIR = ASSET_DIR / "models"

REPO_ROOT = SKILL_DIR.parent
WORK_ROOT = Path(os.environ.get("ANALOG_WORK_DIR", str(REPO_ROOT / "WORK")))
LOG_DIR = WORK_ROOT / "logs"
PLOT_DIR = WORK_ROOT / "plots"
NETLIST_SAVE_DIR = WORK_ROOT / "netlists"
NETLIST_DUT_DIR = NETLIST_SAVE_DIR / "dut"
NETLIST_TB_DIR = NETLIST_SAVE_DIR / "testbench"

for _d in (LOG_DIR, PLOT_DIR, NETLIST_DUT_DIR, NETLIST_TB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def spath(path):
    return str(path).replace("\\", "/")


def find_ngspice():
    for exe in ("ngspice_con", "ngspice"):
        if shutil.which(exe):
            return exe
    return "ngspice"


def check_ngspice():
    exe = find_ngspice()
    proc = subprocess.run([exe, "-v"], capture_output=True, text=True, check=False)
    banner = strip_ansi((proc.stdout or proc.stderr or "").strip()).splitlines()
    if banner:
        print(f"  {banner[0]}")
    return exe


def render_template(tmpl_name, **kwargs):
    text = (NETLIST_DIR / tmpl_name).read_text(encoding="utf-8")
    return text.format(**kwargs)


def run_ngspice(netlist, log=None, timeout=180):
    proc = subprocess.run(
        [find_ngspice(), "-b", str(netlist)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    text = strip_ansi((proc.stdout or "") + (proc.stderr or ""))
    if log:
        Path(log).write_text(text, encoding="utf-8")
    return proc.returncode


def run_rendered_netlist(tmpl_name, kwargs, log_path, timeout=180):
    text = render_template(tmpl_name, **kwargs)
    save_path = NETLIST_TB_DIR / (Path(log_path).stem + ".cir")
    save_path.write_text(text, encoding="utf-8")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cir", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp = f.name
    try:
        return run_ngspice(tmp, log=log_path, timeout=timeout)
    finally:
        os.unlink(tmp)


def parse_wrdata(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        nums = []
        for token in parts:
            try:
                nums.append(float(token))
            except ValueError:
                pass
        if len(nums) >= 2:
            rows.append((nums[0], nums[1]))
    return np.array(rows, dtype=float) if rows else None

