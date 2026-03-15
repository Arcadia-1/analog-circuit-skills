#!/usr/bin/env python3
"""
sweep_inp_width_tcmp.py
=======================
Sweep input pair M1/M2 width from 1 um to 10 um and plot Tcmp vs W_inp.

Saves PNG to the specified output directory.
"""

import os
import math
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# Must chdir to scripts/ so imports resolve correctly
SCRIPTS_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, str(SCRIPTS_DIR))

import comparator_common as cc
from comparator_common import compute_tcmp, TCLK
from simulate_tran_strongarm_wave import simulate_wave, WAVE_NCYC

OUTPUT_DIR = Path("H:/analog-circuit-skills/comparator-workspace/iteration-1/tcmp-vs-input-width/without_skill/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W_RANGE = list(range(1, 11))   # 1 to 10 um

print("=== Sweep W_inp (Input pair M1/M2) from 1 um to 10 um ===")
print(f"Nominal W_inp = {cc.W['inp']} um")
print()

original_inp = cc.W["inp"]
results = []

for w in W_RANGE:
    cc.W["inp"] = w
    print(f"  W_inp = {w} um ...", end="  ", flush=True)
    try:
        r = simulate_wave()
        wv = r["wave"]
        if wv["time"] is not None and wv["outp"] is not None:
            tcmp = compute_tcmp(wv["time"], wv["outp"], WAVE_NCYC)
            tau  = wv.get("tau_ps", float("nan"))
        else:
            tcmp = float("nan")
            tau  = float("nan")
    except Exception as e:
        print(f"ERROR: {e}")
        tcmp = float("nan")
        tau  = float("nan")
    print(f"Tcmp={tcmp:.1f}ps  tau={tau:.1f}ps")
    results.append((w, tcmp, tau))

# Restore original
cc.W["inp"] = original_inp

# ── Extract valid data ─────────────────────────────────────────────────────────
ws   = [r[0] for r in results]
tcmp = [r[1] for r in results]
tau  = [r[2] for r in results]

valid_w_t = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
valid_t   = [t for t in tcmp if not math.isnan(t)]
valid_w_a = [w for w, a in zip(ws, tau)  if not math.isnan(a)]
valid_a   = [a for a in tau  if not math.isnan(a)]

# ── Figure 1: Tcmp vs W_inp ────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(valid_w_t, valid_t, "o-", color="#2ca02c", lw=2,
        ms=8, mfc="white", mew=2.2, zorder=3, label="Tcmp (ps)")

# Mark nominal
nom_w = original_inp
nom_t = next((t for w, t, _ in results if w == nom_w and not math.isnan(t)), None)
if nom_t is not None:
    ax.axvline(nom_w, color="gray", lw=1, ls="--", alpha=0.6)
    ax.plot(nom_w, nom_t, "D", color="#2ca02c", ms=10, zorder=4,
            label=f"Nominal W={nom_w} um  Tcmp={nom_t:.1f}ps")

# Annotate each point
for w, t in zip(valid_w_t, valid_t):
    ax.annotate(f"{t:.0f}", xy=(w, t), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=8, color="#2ca02c")

ax.set_xlabel("W_inp — Input Pair M1/M2 Width (um)", fontsize=11)
ax.set_ylabel("Tcmp (ps)", fontsize=11)
ax.set_title("StrongArm Comparator — Tcmp vs. Input Pair Width\n"
             "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=11)
ax.set_xlim(0.5, 10.5)
ax.set_ylim(bottom=0)
ax.set_xticks(W_RANGE)
ax.grid(True, linestyle="--", alpha=0.45)
ax.legend(fontsize=9, loc="upper right")
ax.tick_params(labelsize=9)

plt.tight_layout()
out1 = OUTPUT_DIR / "tcmp_vs_inp_width.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out1}")
plt.close(fig)

# ── Figure 2: Tcmp + tau overlay ──────────────────────────────────────────────
if valid_a:
    fig2, ax2a = plt.subplots(figsize=(7, 4.5))
    color_t = "#d62728"
    color_a = "#1f77b4"

    l1, = ax2a.plot(valid_w_t, valid_t, "o-", color=color_t, lw=2,
                    ms=8, mfc="white", mew=2.2, label="Tcmp (ps)")
    ax2b = ax2a.twinx()
    l2, = ax2b.plot(valid_w_a, valid_a, "s--", color=color_a, lw=1.8,
                    ms=8, mfc="white", mew=2.2, label="tau (ps)")

    ax2a.set_xlabel("W_inp — Input Pair M1/M2 Width (um)", fontsize=11)
    ax2a.set_ylabel("Tcmp (ps)", color=color_t, fontsize=11)
    ax2b.set_ylabel("Latch tau (ps)", color=color_a, fontsize=11)
    ax2a.tick_params(axis="y", labelcolor=color_t, labelsize=9)
    ax2b.tick_params(axis="y", labelcolor=color_a, labelsize=9)
    ax2a.set_title("StrongArm — Tcmp and tau vs. Input Pair Width\n"
                   "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=11)
    ax2a.set_xlim(0.5, 10.5)
    ax2a.set_ylim(bottom=0)
    ax2b.set_ylim(bottom=0)
    ax2a.set_xticks(W_RANGE)
    ax2a.grid(True, linestyle="--", alpha=0.35)
    lines = [l1, l2]
    ax2a.legend(lines, [l.get_label() for l in lines], fontsize=9, loc="upper right")
    ax2a.tick_params(axis="x", labelsize=9)

    plt.tight_layout()
    out2 = OUTPUT_DIR / "tcmp_tau_vs_inp_width.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight")
    print(f"Saved: {out2}")
    plt.close(fig2)

# ── Print table ───────────────────────────────────────────────────────────────
print()
print(f"{'W_inp (um)':>12}  {'Tcmp (ps)':>10}  {'tau (ps)':>10}")
print("  " + "-" * 36)
for w, t, a in results:
    ts = f"{t:.1f}" if not math.isnan(t) else "N/A"
    as_ = f"{a:.1f}" if not math.isnan(a) else "N/A"
    nom = " <-- nominal" if w == original_inp else ""
    print(f"{w:>12}  {ts:>10}  {as_:>10}{nom}")

# ── Summary ────────────────────────────────────────────────────────────────────
valid_pairs = [(w, t) for w, t, _ in results if not math.isnan(t)]
if valid_pairs:
    w_min_t, t_min = min(valid_pairs, key=lambda x: x[1])
    w_max_t, t_max = max(valid_pairs, key=lambda x: x[1])
    print(f"\nFastest: W_inp={w_min_t} um -> Tcmp={t_min:.1f} ps")
    print(f"Slowest: W_inp={w_max_t} um -> Tcmp={t_max:.1f} ps")
    if t_min > 0:
        print(f"Speedup (1um->fastest): {valid_pairs[0][1]/t_min:.2f}x")

summary_lines = [
    "StrongArm Comparator — Tcmp vs. Input Pair Width Sweep",
    "=" * 55,
    "Technology: 45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV",
    f"Nominal W_inp = {original_inp} um",
    "",
    f"{'W_inp (um)':>12}  {'Tcmp (ps)':>10}  {'tau (ps)':>10}",
    "  " + "-" * 36,
]
for w, t, a in results:
    ts  = f"{t:.1f}" if not math.isnan(t) else "N/A"
    as_ = f"{a:.1f}" if not math.isnan(a) else "N/A"
    nom = "  <-- nominal" if w == original_inp else ""
    summary_lines.append(f"{w:>12}  {ts:>10}  {as_:>10}{nom}")

if valid_pairs:
    summary_lines += [
        "",
        f"Fastest: W_inp={w_min_t} um -> Tcmp={t_min:.1f} ps",
        f"Slowest: W_inp={w_max_t} um -> Tcmp={t_max:.1f} ps",
    ]

summary_lines += [
    "",
    "Key Insight:",
    "  Larger W_inp increases the tail current injected into the latch nodes",
    "  (VXP/VXN), which builds up the initial voltage difference faster,",
    "  reducing Tcmp. However, larger W_inp also increases capacitive load,",
    "  which can slow the latch regeneration (tau). The net effect is that",
    "  Tcmp typically decreases monotonically with W_inp up to a point where",
    "  increased parasitic capacitance diminishes further gains.",
    "",
    "Output files:",
    f"  tcmp_vs_inp_width.png      — Tcmp vs W_inp with annotations",
    f"  tcmp_tau_vs_inp_width.png  — Tcmp and tau overlaid on dual-axis",
    f"  summary.txt                — This file",
]

summary_text = "\n".join(summary_lines)
summary_path = OUTPUT_DIR / "summary.txt"
summary_path.write_text(summary_text, encoding="utf-8")
print(f"\nSaved: {summary_path}")
print("\nDone.")
