#!/usr/bin/env python3
"""
run_tau_sweep_plot.py
=====================
Sweep W_lat_n, W_lat_p, W_inp and save τ plots to WORK/plots/.
"""

import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from simulate_tran_strongarm_wave import simulate_wave

PLOT_DIR = Path("H:/analog-circuit-skills/WORK/plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def run_sweep(param_name, values):
    original = cc.W[param_name]
    results = []
    for w in values:
        cc.W[param_name] = w
        print(f"  W_{param_name} = {w} µm ...", flush=True)
        try:
            r = simulate_wave()
            tau = r["wave"].get("tau_ps", float("nan"))
        except Exception as e:
            print(f"    ERROR: {e}")
            tau = float("nan")
        results.append((w, tau))
    cc.W[param_name] = original
    return results


# ── Run all three sweeps ───────────────────────────────────────────────────────
print("\n=== Sweep W_lat_n ===")
lat_n_w   = list(range(1, 11))   # 1 to 10 µm, step 1
res_lat_n = run_sweep("lat_n", lat_n_w)

print("\n=== Sweep W_lat_p ===")
lat_p_w   = list(range(1, 11))
res_lat_p = run_sweep("lat_p", lat_p_w)

print("\n=== Sweep W_inp ===")
inp_w   = list(range(1, 11))
res_inp = run_sweep("inp", inp_w)


# ── Helper ─────────────────────────────────────────────────────────────────────
def split(res):
    ws  = [w for w, t in res]
    tau = [t if not math.isnan(t) else None for w, t in res]
    return ws, tau


# ── Figure 1: three subplots side by side ─────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
fig.suptitle("StrongArm Comparator — τ vs. Transistor Width\n"
             "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=11)

sweeps = [
    (axes[0], res_lat_n, "W$_{lat,n}$ (µm)", "Latch NMOS M3/M4\n(W_lat_p=2µm, W_inp=4µm)"),
    (axes[1], res_lat_p, "W$_{lat,p}$ (µm)", "Latch PMOS M5/M6\n(W_lat_n=1µm, W_inp=4µm)"),
    (axes[2], res_inp,   "W$_{inp}$ (µm)",   "Input Pair M1/M2\n(W_lat_n=1µm, W_lat_p=2µm)"),
]

for ax, res, xlabel, title in sweeps:
    ws, tau = split(res)
    valid_w   = [w for w, t in zip(ws, tau) if t is not None]
    valid_tau = [t for t in tau if t is not None]
    nan_w     = [w for w, t in zip(ws, tau) if t is None]

    ax.plot(valid_w, valid_tau, "o-", color="#1f77b4", lw=1.8,
            ms=7, mfc="white", mew=2, zorder=3)
    if nan_w:
        ax.plot(nan_w, [0] * len(nan_w), "x", color="red",
                ms=10, mew=2.5, label="NaN (too slow)", zorder=4)
        ax.legend(fontsize=8, loc="upper left")

    # Reference band
    ax.axhspan(24, 36, color="gray", alpha=0.15, label="ref 24–36 ps")

    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("τ (ps)", fontsize=10)
    ax.set_title(title, fontsize=9)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.tick_params(labelsize=9)

plt.tight_layout()
out1 = PLOT_DIR / "tau_sweep_width.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out1}")
plt.close(fig)


# ── Figure 2: combined overlay (lat_n and lat_p on same axes) ─────────────────
fig2, (ax_latch, ax_inp) = plt.subplots(1, 2, figsize=(9, 4))
fig2.suptitle("StrongArm τ — Latch vs. Input-Pair Sizing\n"
              "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz", fontsize=11)

# Latch panel
ws_n, tau_n = split(res_lat_n)
ws_p, tau_p = split(res_lat_p)

vw_n  = [w for w, t in zip(ws_n, tau_n) if t is not None]
vt_n  = [t for t in tau_n if t is not None]
vw_p  = [w for w, t in zip(ws_p, tau_p) if t is not None]
vt_p  = [t for t in tau_p if t is not None]

ax_latch.plot(vw_n, vt_n, "o-", color="#1f77b4", lw=1.8, ms=7,
              mfc="white", mew=2, label="NMOS M3/M4 (W_lat_n)")
ax_latch.plot(vw_p, vt_p, "s-", color="#d62728", lw=1.8, ms=7,
              mfc="white", mew=2, label="PMOS M5/M6 (W_lat_p)")
ax_latch.axhspan(24, 36, color="gray", alpha=0.15, label="ref 24–36 ps")
ax_latch.set_xlabel("Width (µm)", fontsize=10)
ax_latch.set_ylabel("τ (ps)", fontsize=10)
ax_latch.set_title("Latch transistors", fontsize=10)
ax_latch.set_ylim(bottom=0)
ax_latch.legend(fontsize=8)
ax_latch.grid(True, linestyle="--", alpha=0.45)
ax_latch.tick_params(labelsize=9)

# Input pair panel
ws_i, tau_i = split(res_inp)
vw_i  = [w for w, t in zip(ws_i, tau_i) if t is not None]
vt_i  = [t for t in tau_i if t is not None]
nan_i = [w for w, t in zip(ws_i, tau_i) if t is None]

ax_inp.plot(vw_i, vt_i, "^-", color="#2ca02c", lw=1.8, ms=7,
            mfc="white", mew=2, label="Input pair M1/M2")
if nan_i:
    ax_inp.plot(nan_i, [2] * len(nan_i), "x", color="red",
                ms=10, mew=2.5, label=f"NaN (W={nan_i}µm, too slow)")
ax_inp.axhspan(24, 36, color="gray", alpha=0.15, label="ref 24–36 ps")
ax_inp.set_xlabel("W$_{inp}$ (µm)", fontsize=10)
ax_inp.set_ylabel("τ (ps)", fontsize=10)
ax_inp.set_title("Input pair (affects integration phase)", fontsize=10)
ax_inp.set_ylim(bottom=0)
ax_inp.legend(fontsize=8)
ax_inp.grid(True, linestyle="--", alpha=0.45)
ax_inp.tick_params(labelsize=9)

plt.tight_layout()
out2 = PLOT_DIR / "tau_sweep_overlay.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"Saved: {out2}")
plt.close(fig2)

print("\nDone.")
