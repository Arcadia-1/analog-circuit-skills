#!/usr/bin/env python3
"""
run_power_sweep_without_skill.py
================================
Sweep W_tail / W_inp / W_lat_n / W_lat_p (1–10 µm) and plot average power vs. width.
Saves PNGs to the specified output directory.

Power is measured with Vin=0 (balanced input), 10 clock cycles.
Average power = VDD × mean(|i(vvdd)|) over the full simulation window.
"""

import os, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from ngspice_common import LOG_DIR, parse_wrdata, spath

OUTPUT_DIR = Path("H:/analog-circuit-skills/comparator-workspace/iteration-1/power-vs-width-sweep/without_skill/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PWR_NCYC  = 10
PWR_TSTOP = PWR_NCYC * cc.TCLK    # 10 ns
PWR_TSTEP = 50e-12                 # 50 ps

W_RANGE = list(range(1, 11))      # 1–10 µm, step 1 µm


def simulate_power() -> float:
    """
    Run 10-cycle Vin=0 simulation, return average power in µW.
    Uses testbench_cmp_tran_noise.cir.tmpl (with trnoise injected)
    but with Vin_diff = 0.
    """
    dut_include, dut_tmp = cc.render_dut()
    try:
        ivdd_path = LOG_DIR / "power_sweep_ivdd.txt"
        out_path  = LOG_DIR / "power_sweep_outp.txt"
        ivdd_cmd  = f"wrdata {spath(ivdd_path)} i(vvdd)"

        kw = dict(
            **cc.common_kw(dut_include),
            vin_label = 0.0,
            inp_src   = f"VINP_DC INP_DC 0 DC {cc.VCM:.10f}",
            inn_src   = f"VINN_DC INN_DC 0 DC {cc.VCM:.10f}",
            tstep     = f"{PWR_TSTEP:.4e}",
            tstop     = f"{PWR_TSTOP:.4e}",
            out_outp  = spath(out_path),
            ivdd_cmd  = ivdd_cmd,
        )
        rc = cc.run_netlist("testbench_cmp_tran_noise.cir.tmpl", kw,
                            LOG_DIR / "power_sweep.log", timeout=120)

        if rc != 0 or not ivdd_path.exists():
            return float("nan")

        ivdd_raw = parse_wrdata(ivdd_path)
        if ivdd_raw is None or len(ivdd_raw) < 10:
            return float("nan")

        return cc.VDD * np.mean(np.abs(ivdd_raw[:, 1])) * 1e6   # µW

    finally:
        if dut_tmp:
            os.unlink(dut_tmp)


def run_sweep(param_name, values):
    original = cc.W[param_name]
    results  = []
    for w in values:
        cc.W[param_name] = w
        print(f"  W_{param_name} = {w} µm ...", end="  ", flush=True)
        try:
            p = simulate_power()
        except Exception as e:
            print(f"ERROR: {e}")
            p = float("nan")
        tag = f"{p:.2f} µW" if not math.isnan(p) else "NaN"
        print(f"P_avg = {tag}")
        results.append((w, p))
    cc.W[param_name] = original
    return results


# ── Sweeps ─────────────────────────────────────────────────────────────────────
sweeps_cfg = [
    ("tail",  "Tail switch M0"),
    ("inp",   "Input pair M1/M2"),
    ("lat_n", "Latch NMOS M3/M4"),
    ("lat_p", "Latch PMOS M5/M6"),
]

data = {}
for key, label in sweeps_cfg:
    print(f"\n=== Sweep W_{key} ===")
    data[key] = run_sweep(key, W_RANGE)


# ── Figure 1: 2×2 subplots ─────────────────────────────────────────────────────
colors = {"tail": "#1f77b4", "inp": "#2ca02c", "lat_n": "#d62728", "lat_p": "#9467bd"}

fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=False)
fig.suptitle("StrongArm Comparator — Average Power vs. Transistor Width\n"
             "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=0 V  (10 cycles)", fontsize=12)

ax_map = {"tail": axes[0, 0], "inp": axes[0, 1],
          "lat_n": axes[1, 0], "lat_p": axes[1, 1]}

for key, label in sweeps_cfg:
    ax  = ax_map[key]
    res = data[key]
    ws  = [r[0] for r in res]
    pw  = [r[1] for r in res]

    vw = [w for w, p in zip(ws, pw) if not math.isnan(p)]
    vp = [p for p in pw if not math.isnan(p)]

    ax.plot(vw, vp, "o-", color=colors[key], lw=2,
            ms=7, mfc="white", mew=2.2, zorder=3)

    nom_w = cc.W[key]
    nom_p = next((p for w, p in res if w == nom_w), None)
    if nom_p is not None and not math.isnan(nom_p):
        ax.axvline(nom_w, color="gray", lw=1, ls="--", alpha=0.6)
        ax.plot(nom_w, nom_p, "D", color=colors[key], ms=9, zorder=4,
                label=f"nominal W={nom_w}µm")

    ax.set_xlabel("Width (µm)", fontsize=10)
    ax.set_ylabel("P_avg (µW)", fontsize=10)
    ax.set_title(label, fontsize=10)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.legend(fontsize=8, loc="best")
    ax.tick_params(labelsize=9)

plt.tight_layout()
out1 = OUTPUT_DIR / "power_sweep_width.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out1}")
plt.close(fig)


# ── Figure 2: all four curves on one axes ──────────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(7, 4.5))
fig2.suptitle("StrongArm — P_avg vs. Width (all devices)\n"
              "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=0 V", fontsize=11)

markers = {"tail": "o", "inp": "^", "lat_n": "s", "lat_p": "D"}
labels  = {"tail": "Tail M0", "inp": "Input pair M1/M2",
           "lat_n": "Latch NMOS M3/M4", "lat_p": "Latch PMOS M5/M6"}

for key, _ in sweeps_cfg:
    res = data[key]
    ws  = [r[0] for r in res]
    pw  = [r[1] for r in res]
    vw  = [w for w, p in zip(ws, pw) if not math.isnan(p)]
    vp  = [p for p in pw if not math.isnan(p)]
    ax2.plot(vw, vp, markers[key] + "-", color=colors[key], lw=1.8,
             ms=7, mfc="white", mew=2, label=labels[key])

ax2.set_xlabel("Width (µm)", fontsize=10)
ax2.set_ylabel("P_avg (µW)", fontsize=10)
ax2.set_title("All devices — power sensitivity", fontsize=10)
ax2.set_ylim(bottom=0)
ax2.grid(True, linestyle="--", alpha=0.45)
ax2.legend(fontsize=9)
ax2.tick_params(labelsize=9)

plt.tight_layout()
out2 = OUTPUT_DIR / "power_sweep_all.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"Saved: {out2}")
plt.close(fig2)


# ── Collect numeric results and write summary ───────────────────────────────────
summary_lines = []
summary_lines.append("Power vs. Width Sweep — Numeric Results")
summary_lines.append("=" * 50)
summary_lines.append(f"Circuit: StrongArm, 45nm PTM HP, VDD=1.0V, FCLK=1GHz, Vin=0V, 10 cycles")
summary_lines.append(f"Width range: 1–10 µm (step 1 µm)\n")

for key, label in sweeps_cfg:
    nom_w = {
        "tail": 4.0, "inp": 4.0, "lat_n": 1.0, "lat_p": 2.0
    }[key]
    res = data[key]
    summary_lines.append(f"--- {label} (nominal W={nom_w}µm) ---")
    for w, p in res:
        marker = " <-- nominal" if w == nom_w else ""
        tag = f"{p:.2f} µW" if not math.isnan(p) else "NaN"
        summary_lines.append(f"  W={w:2d} µm:  P_avg = {tag}{marker}")
    # Sensitivity at nominal
    valid = [(w, p) for w, p in res if not math.isnan(p)]
    if len(valid) >= 2:
        ws = [r[0] for r in valid]
        ps = [r[1] for r in valid]
        dp = ps[-1] - ps[0]
        dw = ws[-1] - ws[0]
        sens = dp / dw
        summary_lines.append(f"  Sensitivity (1–10µm): dP/dW = {sens:.2f} µW/µm")
    summary_lines.append("")

summary_text = "\n".join(summary_lines)
summary_path = OUTPUT_DIR / "summary.txt"
summary_path.write_text(summary_text, encoding="utf-8")
print(f"Saved: {summary_path}")

print("\nDone.")
