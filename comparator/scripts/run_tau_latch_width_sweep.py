#!/usr/bin/env python3
"""
run_tau_latch_width_sweep.py
============================
Sweep W_lat_n (M3/M4, latch NMOS) and W_lat_p (M5/M6, latch PMOS) from 1 to 10 µm
and measure the latch regeneration time constant τ for each.
Produces two plots saved to the specified output directory.
"""

import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# Run from the scripts directory so imports work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from simulate_tran_strongarm_wave import simulate_wave

OUTPUT_DIR = Path(os.environ.get(
    "TAU_SWEEP_OUTPUT_DIR",
    "H:/analog-circuit-skills/comparator-workspace/iteration-1/tau-vs-latch-width/without_skill/outputs"
))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_sweep(param_name, values):
    """Sweep one width parameter, return list of (w_um, tau_ps)."""
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


def split(res):
    ws  = [w for w, t in res]
    tau = [t if not math.isnan(t) else None for w, t in res]
    return ws, tau


# ── Run sweeps ─────────────────────────────────────────────────────────────────
widths = list(range(1, 11))   # 1 … 10 µm

print("\n=== Sweeping W_lat_n (NMOS latch M3/M4) ===")
print(f"    Fixed: W_lat_p={cc.W['lat_p']} µm, W_inp={cc.W['inp']} µm")
res_lat_n = run_sweep("lat_n", widths)

print("\n=== Sweeping W_lat_p (PMOS latch M5/M6) ===")
print(f"    Fixed: W_lat_n={cc.W['lat_n']} µm, W_inp={cc.W['inp']} µm")
res_lat_p = run_sweep("lat_p", widths)

# Print tabular summary
print("\n─── Summary ────────────────────────────────────────")
print(f"{'W (µm)':>8}  {'τ_NMOS (ps)':>12}  {'τ_PMOS (ps)':>12}")
print(f"{'-------':>8}  {'----------':>12}  {'----------':>12}")
for (wn, tn), (wp, tp) in zip(res_lat_n, res_lat_p):
    tn_str = f"{tn:.1f}" if not math.isnan(tn) else "NaN"
    tp_str = f"{tp:.1f}" if not math.isnan(tp) else "NaN"
    print(f"{wn:>8}  {tn_str:>12}  {tp_str:>12}")

# ── Figure 1: side-by-side subplots ───────────────────────────────────────────
fig, (ax_n, ax_p) = plt.subplots(1, 2, figsize=(10, 4.5))
fig.suptitle(
    "StrongArm Comparator — τ vs. Latch Transistor Width\n"
    "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV",
    fontsize=11,
)

for ax, res, label, color, fixed_info, param_label in [
    (ax_n, res_lat_n, "NMOS latch M3/M4", "#1f77b4",
     f"W_lat_p={cc.W['lat_p']} µm, W_inp={cc.W['inp']} µm", "W$_{{lat,n}}$ (µm)"),
    (ax_p, res_lat_p, "PMOS latch M5/M6", "#d62728",
     f"W_lat_n={cc.W['lat_n']} µm, W_inp={cc.W['inp']} µm", "W$_{{lat,p}}$ (µm)"),
]:
    ws, tau = split(res)
    valid_w   = [w for w, t in zip(ws, tau) if t is not None]
    valid_tau = [t for t in tau if t is not None]
    nan_w     = [w for w, t in zip(ws, tau) if t is None]

    ax.plot(valid_w, valid_tau, "o-", color=color, lw=2, ms=8,
            mfc="white", mew=2, zorder=3)
    if nan_w:
        ax.plot(nan_w, [2] * len(nan_w), "x", color="red",
                ms=10, mew=2.5, label="NaN (sim failed)", zorder=4)
        ax.legend(fontsize=8, loc="upper right")

    # Reference band (nominal τ range)
    ax.axhspan(24, 36, color="gray", alpha=0.15, label="ref 24–36 ps")

    # Mark nominal operating point
    nom_w = cc.W["lat_n"] if "lat_n" in param_label else cc.W["lat_p"]
    for w, t in zip(ws, tau):
        if w == nom_w and t is not None:
            ax.axvline(x=w, color=color, lw=1, ls=":", alpha=0.7)
            ax.annotate(f"nominal\nW={w}µm\nτ={t:.0f}ps",
                        xy=(w, t), xytext=(w + 0.8, t + 3),
                        fontsize=7.5, color=color,
                        arrowprops=dict(arrowstyle="->", color=color, lw=0.8))

    ax.set_xlabel(param_label, fontsize=10)
    ax.set_ylabel("τ (ps)", fontsize=10)
    ax.set_title(f"{label}\n({fixed_info})", fontsize=9)
    ax.set_xlim(0.5, 10.5)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.tick_params(labelsize=9)

plt.tight_layout()
out1 = OUTPUT_DIR / "tau_vs_latch_width_sidebyside.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: {out1}")

# ── Figure 2: overlay both latch sweeps on one axes ───────────────────────────
fig2, ax = plt.subplots(figsize=(7, 4.5))
fig2.suptitle(
    "StrongArm τ — NMOS M3/M4 vs. PMOS M5/M6 Latch Width\n"
    "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV",
    fontsize=11,
)

ws_n, tau_n = split(res_lat_n)
ws_p, tau_p = split(res_lat_p)

vw_n  = [w for w, t in zip(ws_n, tau_n) if t is not None]
vt_n  = [t for t in tau_n if t is not None]
vw_p  = [w for w, t in zip(ws_p, tau_p) if t is not None]
vt_p  = [t for t in tau_p if t is not None]

ax.plot(vw_n, vt_n, "o-", color="#1f77b4", lw=2, ms=8,
        mfc="white", mew=2,
        label=f"NMOS M3/M4  W_lat_n  (fixed W_lat_p={cc.W['lat_p']}µm)")
ax.plot(vw_p, vt_p, "s-", color="#d62728", lw=2, ms=8,
        mfc="white", mew=2,
        label=f"PMOS M5/M6  W_lat_p  (fixed W_lat_n={cc.W['lat_n']}µm)")

ax.axhspan(24, 36, color="gray", alpha=0.15, label="ref τ = 24–36 ps")
ax.axvline(x=cc.W["lat_n"], color="#1f77b4", lw=1, ls=":", alpha=0.6)
ax.axvline(x=cc.W["lat_p"], color="#d62728", lw=1, ls=":", alpha=0.6)

ax.set_xlabel("Transistor Width (µm)", fontsize=11)
ax.set_ylabel("τ (ps)", fontsize=11)
ax.set_title("Effect of latch transistor width on τ\n"
             "(other widths held at nominal)", fontsize=10)
ax.set_xlim(0.5, 10.5)
ax.set_ylim(bottom=0)
ax.legend(fontsize=9, loc="upper right")
ax.grid(True, linestyle="--", alpha=0.45)
ax.tick_params(labelsize=10)

plt.tight_layout()
out2 = OUTPUT_DIR / "tau_vs_latch_width_overlay.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {out2}")

# ── Write data table as text file ─────────────────────────────────────────────
table_path = OUTPUT_DIR / "tau_data_table.txt"
with open(table_path, "w") as f:
    f.write("W (µm)  τ_NMOS M3/M4 (ps)  τ_PMOS M5/M6 (ps)\n")
    f.write("------  -----------------  -----------------\n")
    for (wn, tn), (wp, tp) in zip(res_lat_n, res_lat_p):
        tn_str = f"{tn:.2f}" if not math.isnan(tn) else "NaN"
        tp_str = f"{tp:.2f}" if not math.isnan(tp) else "NaN"
        f.write(f"{wn:>6}  {tn_str:>17}  {tp_str:>17}\n")
print(f"Saved: {table_path}")

print("\nDone.")
