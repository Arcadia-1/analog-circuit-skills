#!/usr/bin/env python3
"""
run_tcmp_sweep_plot.py
======================
Sweep W_tail / W_inp / W_lat_n / W_lat_p and plot Tcmp vs width.

Tcmp is measured from the 3-cycle waveform simulation (fast, 2ps timestep)
using compute_tcmp() — average CLK→OUTP(VDD/2) crossing time over WAVE_NCYC cycles.

Run from comparator/assets/:
    python run_tcmp_sweep_plot.py
"""

import os, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from comparator_common import compute_tcmp, TCLK
from simulate_tran_strongarm_wave import simulate_wave, WAVE_NCYC

import os as _os
_work_root = Path(_os.environ.get("ANALOG_WORK_DIR",
                                   "H:/analog-circuit-skills/WORK"))
PLOT_DIR = _work_root / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

W_RANGE = list(range(1, 11))   # 1–10 µm, step 1 µm


def run_sweep(param_name, values):
    original = cc.W[param_name]
    results = []
    for w in values:
        cc.W[param_name] = w
        print(f"  W_{param_name} = {w} µm ...", end="  ", flush=True)
        try:
            r = simulate_wave()
            wv = r["wave"]
            if wv["time"] is not None and wv["outp"] is not None:
                tcmp = compute_tcmp(wv["time"], wv["outp"], WAVE_NCYC)
            else:
                tcmp = float("nan")
        except Exception as e:
            print(f"ERROR: {e}")
            tcmp = float("nan")
        tau = wv.get("tau_ps", float("nan")) if "wv" in dir() else float("nan")
        print(f"Tcmp={tcmp:.1f}ps  τ={tau:.1f}ps")
        results.append((w, tcmp, tau))
    cc.W[param_name] = original
    return results


# ── Sweeps ────────────────────────────────────────────────────────────────────
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


# ── Figure: 2×2 Tcmp subplots ─────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=False)
fig.suptitle("StrongArm Comparator — Tcmp vs. Transistor Width\n"
             "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=12)

colors = {"tail": "#1f77b4", "inp": "#2ca02c", "lat_n": "#d62728", "lat_p": "#9467bd"}
ax_map = {"tail": axes[0,0], "inp": axes[0,1], "lat_n": axes[1,0], "lat_p": axes[1,1]}

# Nominal Tcmp reference (from current W settings)
NOM_TCMP = None

for key, label in sweeps_cfg:
    ax = ax_map[key]
    res = data[key]
    ws   = [r[0] for r in res]
    tcmp = [r[1] for r in res]

    valid_w = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
    valid_t = [t for t in tcmp if not math.isnan(t)]

    ax.plot(valid_w, valid_t, "o-", color=colors[key], lw=2,
            ms=7, mfc="white", mew=2.2, zorder=3)

    # Mark nominal operating point
    nom_w = cc.W[key]
    nom_t = next((t for w, t, _ in res if w == nom_w), None)
    if nom_t and not math.isnan(nom_t):
        ax.axvline(nom_w, color="gray", lw=1, ls="--", alpha=0.6)
        ax.plot(nom_w, nom_t, "D", color=colors[key], ms=9, zorder=4,
                label=f"nominal W={nom_w}µm")

    ax.set_xlabel("Width (µm)", fontsize=10)
    ax.set_ylabel("Tcmp (ps)", fontsize=10)
    ax.set_title(label, fontsize=10)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.legend(fontsize=8, loc="best")
    ax.tick_params(labelsize=9)

plt.tight_layout()
out1 = PLOT_DIR / "tcmp_sweep_width.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out1}")
plt.close(fig)


# ── Figure 2: Tcmp + τ overlay on same axes for latch devices ─────────────────
fig2, axes2 = plt.subplots(1, 2, figsize=(10, 4.5))
fig2.suptitle("StrongArm — Tcmp and τ vs. Latch Width\n"
              "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=11)

for ax, key, label in [(axes2[0], "lat_n", "Latch NMOS M3/M4"),
                        (axes2[1], "lat_p", "Latch PMOS M5/M6")]:
    res = data[key]
    ws   = [r[0] for r in res]
    tcmp = [r[1] for r in res]
    tau  = [r[2] for r in res]

    vw_t = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
    vt   = [t for t in tcmp if not math.isnan(t)]
    vw_a = [w for w, t in zip(ws, tau)  if not math.isnan(t)]
    va   = [t for t in tau  if not math.isnan(t)]

    l1, = ax.plot(vw_t, vt, "o-", color="#d62728", lw=2, ms=7,
                  mfc="white", mew=2, label="Tcmp (ps)")
    ax2 = ax.twinx()
    l2, = ax2.plot(vw_a, va, "s--", color="#1f77b4", lw=1.8, ms=7,
                   mfc="white", mew=2, label="τ (ps)")

    ax.set_xlabel("Width (µm)", fontsize=10)
    ax.set_ylabel("Tcmp (ps)", color="#d62728", fontsize=10)
    ax2.set_ylabel("τ (ps)", color="#1f77b4", fontsize=10)
    ax.tick_params(axis="y", labelcolor="#d62728", labelsize=9)
    ax2.tick_params(axis="y", labelcolor="#1f77b4", labelsize=9)
    ax.set_title(label, fontsize=10)
    ax.set_ylim(bottom=0)
    ax2.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.35)
    lines = [l1, l2]
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="upper left")

plt.tight_layout()
out2 = PLOT_DIR / "tcmp_tau_latch_overlay.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"Saved: {out2}")
plt.close(fig2)


# ── Figure 3: all four Tcmp curves on one axes (normalized) ───────────────────
fig3, ax3 = plt.subplots(figsize=(7, 4.5))
fig3.suptitle("StrongArm — Tcmp vs. Width (all devices)\n"
              "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=11)

markers = {"tail": "o", "inp": "^", "lat_n": "s", "lat_p": "D"}
labels  = {"tail": "Tail M0", "inp": "Input pair M1/M2",
           "lat_n": "Latch NMOS M3/M4", "lat_p": "Latch PMOS M5/M6"}

for key, _ in sweeps_cfg:
    res = data[key]
    ws   = [r[0] for r in res]
    tcmp = [r[1] for r in res]
    vw = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
    vt = [t for t in tcmp if not math.isnan(t)]
    ax3.plot(vw, vt, markers[key] + "-", color=colors[key], lw=1.8,
             ms=7, mfc="white", mew=2, label=labels[key])

ax3.set_xlabel("Width (µm)", fontsize=10)
ax3.set_ylabel("Tcmp (ps)", fontsize=10)
ax3.set_title("All devices — Tcmp sensitivity", fontsize=10)
ax3.set_ylim(bottom=0)
ax3.grid(True, linestyle="--", alpha=0.45)
ax3.legend(fontsize=9)
ax3.tick_params(labelsize=9)

plt.tight_layout()
out3 = PLOT_DIR / "tcmp_sweep_all.png"
fig3.savefig(out3, dpi=150, bbox_inches="tight")
print(f"Saved: {out3}")
plt.close(fig3)

print("\nDone.")
