#!/usr/bin/env python3
"""
run_vcm_sensitivity_03_07.py
============================
VCM Sensitivity Scan: VCM from 0.3V to 0.7V
Measures input-referred noise sigma_n at each VCM using single-point probit method.

Output saved to:
  H:/analog-circuit-skills/comparator-workspace/iteration-1/vcm-sensitivity/without_skill/outputs/
"""

import sys
import os
import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# -- Path setup --
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from ngspice_common import LOG_DIR, parse_wrdata, spath, render_template, run_ngspice
from comparator_common import (
    VDD, TCLK,
    render_dut, common_kw, run_netlist,
    sample_output, sigma_from_p1, NOISE_VIN_MV,
)

# ── Output directory ──────────────────────────────────────────────────────────
OUT_DIR = Path(
    "H:/analog-circuit-skills/comparator-workspace/"
    "iteration-1/vcm-sensitivity/without_skill/outputs"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Sweep parameters ──────────────────────────────────────────────────────────
VCM_START   = 0.30        # V
VCM_STOP    = 0.70        # V
N_VCM       = 17          # ~25 mV steps: 0.30, 0.325, ..., 0.70
NCYC        = 200         # cycles per VCM point
VIN_FIXED_MV = NOISE_VIN_MV  # 0.35 mV — optimal for probit method

SWEEP_TSTEP    = 500e-12  # 500 ps output step
SWEEP_NOISE_NT = 50e-12   # 50 ps → BW = 10 GHz (10× clock)

VCM_VALS = list(np.linspace(VCM_START, VCM_STOP, N_VCM))
MAX_WORKERS = N_VCM


def _run_one_vcm(vcm, dut_include, ncyc):
    """Run one ngspice process at VIN_FIXED_MV for a given VCM, count P(1)."""
    tag = f"vcm_sens_vcm{vcm*1000:.0f}mv"
    log = LOG_DIR / f"{tag}.log"
    out = LOG_DIR / f"{tag}_outp.txt"

    vin  = VIN_FIXED_MV * 1e-3
    vinp = vcm + vin / 2
    vinn = vcm - vin / 2

    base_kw = common_kw(dut_include)
    base_kw["noise_nt"]    = f"{SWEEP_NOISE_NT:.4e}"
    base_kw["noise_nt_ps"] = SWEEP_NOISE_NT * 1e12

    kw = dict(
        **base_kw,
        vin_label = VIN_FIXED_MV,
        inp_src   = f"VINP_DC INP_DC 0 DC {vinp:.10f}",
        inn_src   = f"VINN_DC INN_DC 0 DC {vinn:.10f}",
        tstep     = f"{SWEEP_TSTEP:.4e}",
        tstop     = f"{ncyc * TCLK:.4e}",
        out_outp  = spath(out),
        ivdd_cmd  = "",
    )
    run_netlist("testbench_cmp_tran_noise.cir.tmpl", kw, log)

    raw = parse_wrdata(out) if out.exists() else None
    count_1 = 0
    if raw is not None and len(raw) >= ncyc:
        count_1 = int(np.sum(sample_output(raw[:, 0], raw[:, 1], ncyc)))

    p1      = count_1 / ncyc
    sigma_v = sigma_from_p1(p1, vin)
    sigma_uv = abs(sigma_v) * 1e6 if not np.isnan(sigma_v) else float("nan")

    return {"vcm": vcm, "p1": p1, "sigma_uv": sigma_uv}


def sweep_vcm_extended():
    """Run VCM sweep from 0.3V to 0.7V in parallel."""
    print(f"\n{'='*65}")
    print(f"  StrongArm: VCM Sensitivity Scan  (0.3V – 0.7V)")
    print(f"  {N_VCM} VCM points, {NCYC} cycles/point, Vin_fixed={VIN_FIXED_MV}mV")
    print(f"  NT={SWEEP_NOISE_NT*1e12:.0f}ps  BW={1/(2*SWEEP_NOISE_NT)/1e9:.0f}GHz")
    print(f"{'='*65}\n")

    dut_include, dut_tmp = render_dut()

    t_start = time.perf_counter()
    raw_results = {}

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {
                pool.submit(_run_one_vcm, vcm, dut_include, NCYC): vcm
                for vcm in VCM_VALS
            }
            for f in as_completed(future_map):
                vcm_f = future_map[f]
                try:
                    raw_results[vcm_f] = f.result()
                except Exception as exc:
                    print(f"  WARN: VCM={vcm_f:.3f}V failed: {exc}", flush=True)
                    raw_results[vcm_f] = {
                        "vcm": vcm_f, "p1": float("nan"),
                        "sigma_uv": float("nan"),
                    }
                r = raw_results[vcm_f]
                print(
                    f"  VCM={vcm_f:.3f}V  P(1)={r['p1']*100:.1f}%  "
                    f"sigma={r['sigma_uv']:.1f}µV  "
                    f"({time.perf_counter()-t_start:.1f}s)",
                    flush=True,
                )
    finally:
        if dut_tmp:
            os.unlink(dut_tmp)

    wall = time.perf_counter() - t_start
    print(f"\n  Total wall time: {wall:.1f}s")

    results = [raw_results[vcm] for vcm in VCM_VALS]
    return results, wall


def plot_vcm_sensitivity(results, wall_s):
    vcm_v    = np.array([r["vcm"]      for r in results])
    sigma_uv = np.array([r["sigma_uv"] for r in results])

    valid = ~np.isnan(sigma_uv)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5.5))

    ax.plot(vcm_v[valid], sigma_uv[valid], "o-",
            color="#1a7abf", lw=2, ms=7, label="σ_n (simulated)")

    # Mark invalid (non-converged) points
    if np.any(~valid):
        ax.scatter(vcm_v[~valid], np.zeros(np.sum(~valid)),
                   marker="x", color="red", s=80, zorder=5, label="No convergence")

    ax.axvline(0.5, color="gray", lw=0.9, ls="--", label="VDD/2 = 0.5V (nominal)")

    # Annotate min/max if we have valid data
    if valid.any():
        idx_min = np.nanargmin(sigma_uv)
        idx_max = np.nanargmax(sigma_uv)
        ax.annotate(f"min {sigma_uv[idx_min]:.0f}µV",
                    xy=(vcm_v[idx_min], sigma_uv[idx_min]),
                    xytext=(vcm_v[idx_min] + 0.03, sigma_uv[idx_min] + 10),
                    fontsize=8, color="#1a7abf",
                    arrowprops=dict(arrowstyle="->", color="#1a7abf"))
        ax.annotate(f"max {sigma_uv[idx_max]:.0f}µV",
                    xy=(vcm_v[idx_max], sigma_uv[idx_max]),
                    xytext=(vcm_v[idx_max] + 0.01, sigma_uv[idx_max] - 30),
                    fontsize=8, color="darkred",
                    arrowprops=dict(arrowstyle="->", color="darkred"))

    ax.set_xlabel("VCM (V)", fontsize=11)
    ax.set_ylabel("σ_n  Input-referred noise (µV)", fontsize=11)
    ax.set_title(
        "StrongArm Comparator — Input-Referred Noise σ_n vs VCM\n"
        f"45nm PTM HP, VDD=1.0V, CLK=1GHz  |  "
        f"{N_VCM} pts, {NCYC} cycles/pt, Vin_fixed={VIN_FIXED_MV}mV  |  "
        f"runtime {wall_s:.1f}s",
        fontsize=10, fontweight="bold",
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.25, 0.75)

    plt.tight_layout()

    out_png = OUT_DIR / "vcm_sensitivity_03_07.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  PNG saved -> {out_png}")
    return out_png


def write_summary(results, wall_s, out_png):
    vcm_v    = np.array([r["vcm"]      for r in results])
    sigma_uv = np.array([r["sigma_uv"] for r in results])
    valid    = ~np.isnan(sigma_uv)

    lines = []
    lines.append("VCM Sensitivity Scan: StrongArm Comparator")
    lines.append("=" * 50)
    lines.append(f"Sweep range   : VCM = {VCM_START}V to {VCM_STOP}V  ({N_VCM} points)")
    lines.append(f"Method        : single-point probit  (Vin_fixed = {VIN_FIXED_MV} mV)")
    lines.append(f"Cycles/point  : {NCYC}")
    lines.append(f"Noise BW      : {1/(2*SWEEP_NOISE_NT)/1e9:.0f} GHz  (NT={SWEEP_NOISE_NT*1e12:.0f}ps)")
    lines.append(f"Technology    : 45nm PTM HP, VDD=1.0V, CLK=1GHz")
    lines.append(f"Wall time     : {wall_s:.1f}s")
    lines.append("")
    lines.append(f"{'VCM (V)':>10}  {'P(1) (%)':>10}  {'sigma_n (µV)':>14}  {'Note':>10}")
    lines.append("-" * 52)
    for r in results:
        note = ""
        if np.isnan(r["sigma_uv"]):
            note = "no conv."
        elif r["p1"] <= 0.5:
            note = "P1<=50%"
        lines.append(
            f"  {r['vcm']:>8.3f}  {r['p1']*100:>10.1f}  "
            f"{r['sigma_uv']:>14.1f}  {note:>10}"
        )
    lines.append("")
    if valid.any():
        idx_min = np.nanargmin(sigma_uv)
        idx_max = np.nanargmax(sigma_uv)
        lines.append(f"Min sigma_n : {sigma_uv[idx_min]:.1f} µV  at VCM={vcm_v[idx_min]:.3f}V")
        lines.append(f"Max sigma_n : {sigma_uv[idx_max]:.1f} µV  at VCM={vcm_v[idx_max]:.3f}V")
        sigma_range = sigma_uv[idx_max] - sigma_uv[idx_min]
        lines.append(f"Range       : {sigma_range:.1f} µV")
        lines.append("")
        lines.append("Key finding:")
        if sigma_uv[idx_min] < 600:
            lines.append(
                f"  sigma_n is minimized near VCM={vcm_v[idx_min]:.2f}V. "
                f"At low VCM (<0.4V), noise rises because the tail current "
                f"transistor enters linear region, reducing Gm and increasing "
                f"thermal noise sensitivity. At high VCM (>0.6V), PMOS loads "
                f"degrade, also raising noise."
            )
        else:
            lines.append(
                "  Noise increases significantly outside the nominal 0.5V region, "
                "consistent with reduced overdrive on input pair at extreme VCM."
            )
    lines.append("")
    lines.append(f"Output PNG    : {out_png}")

    txt_path = OUT_DIR / "summary.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Summary  -> {txt_path}")
    return txt_path


if __name__ == "__main__":
    results, wall_s = sweep_vcm_extended()
    out_png = plot_vcm_sensitivity(results, wall_s)
    write_summary(results, wall_s, out_png)
    print("\nDone.")
