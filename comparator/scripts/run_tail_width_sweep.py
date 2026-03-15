#!/usr/bin/env python3
"""
run_tail_width_sweep.py
=======================
Sweep tail transistor M0 width from 1 to 10 µm and plot Tcmp vs W_tail.

Saves output PNG to the specified output directory.
"""

import os, math, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# Ensure we run from the scripts directory so imports work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from comparator_common import compute_tcmp, TCLK
from simulate_tran_strongarm_wave import simulate_wave, WAVE_NCYC

OUTPUT_DIR = Path("H:/analog-circuit-skills/comparator-workspace/iteration-1/tcmp-vs-tail-width/without_skill/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W_RANGE = list(range(1, 11))   # 1–10 µm, step 1 µm

print("=" * 60)
print("Sweep: W_tail (M0) from 1 µm to 10 µm")
print(f"Other widths fixed: W_inp={cc.W['inp']}µm, W_lat_n={cc.W['lat_n']}µm, W_lat_p={cc.W['lat_p']}µm")
print("=" * 60)

original_tail = cc.W["tail"]
results = []

for w in W_RANGE:
    cc.W["tail"] = w
    print(f"\n  W_tail = {w} µm ...", flush=True)
    try:
        r = simulate_wave()
        wv = r["wave"]
        if wv["time"] is not None and wv["outp"] is not None:
            tcmp = compute_tcmp(wv["time"], wv["outp"], WAVE_NCYC)
        else:
            tcmp = float("nan")
        tau_ps = wv.get("tau_ps", float("nan"))
    except Exception as e:
        print(f"  ERROR: {e}")
        tcmp = float("nan")
        tau_ps = float("nan")
    print(f"  => Tcmp = {tcmp:.1f} ps,  tau = {tau_ps:.1f} ps")
    results.append((w, tcmp, tau_ps))

cc.W["tail"] = original_tail

# ── Extract valid data ──────────────────────────────────────────────────────
ws    = [r[0] for r in results]
tcmps = [r[1] for r in results]
taus  = [r[2] for r in results]

valid_w    = [w for w, t in zip(ws, tcmps) if not math.isnan(t)]
valid_tcmp = [t for t in tcmps if not math.isnan(t)]
valid_w_t  = [w for w, t in zip(ws, taus) if not math.isnan(t)]
valid_tau  = [t for t in taus if not math.isnan(t)]

print("\n" + "=" * 60)
print("Results summary:")
print(f"{'W_tail (µm)':<14} {'Tcmp (ps)':<12} {'tau (ps)':<10}")
print("-" * 36)
for w, tc, ta in results:
    tc_s = f"{tc:.1f}" if not math.isnan(tc) else "N/A"
    ta_s = f"{ta:.1f}" if not math.isnan(ta) else "N/A"
    print(f"  {w:<12} {tc_s:<12} {ta_s:<10}")
print("=" * 60)

# ── Figure 1: Tcmp vs W_tail ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
fig.suptitle("StrongArm Comparator — Tcmp vs. Tail Width (M0)\n"
             "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=12)

ax.plot(valid_w, valid_tcmp, "o-", color="#1f77b4", lw=2.2,
        ms=8, mfc="white", mew=2.5, zorder=3, label="Tcmp")

# Mark nominal point (original 4 µm)
nom_w = 4
nom_t = next((t for w, t in zip(ws, tcmps) if w == nom_w and not math.isnan(t)), None)
if nom_t is not None:
    ax.axvline(nom_w, color="gray", lw=1, ls="--", alpha=0.6)
    ax.plot(nom_w, nom_t, "D", color="#1f77b4", ms=10, zorder=4,
            label=f"Nominal W=4 µm\nTcmp={nom_t:.0f} ps")

ax.set_xlabel("W_tail / µm", fontsize=11)
ax.set_ylabel("Tcmp (ps)", fontsize=11)
ax.set_title("Tail switch M0 width vs. comparison time", fontsize=10)
ax.set_xlim(0.5, 10.5)
ax.set_ylim(bottom=0)
ax.set_xticks(W_RANGE)
ax.grid(True, linestyle="--", alpha=0.45)
ax.legend(fontsize=9, loc="upper right")
ax.tick_params(labelsize=10)

plt.tight_layout()
out1 = OUTPUT_DIR / "tcmp_vs_tail_width.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: {out1}")

# ── Figure 2: Tcmp + tau overlay ────────────────────────────────────────────
fig2, ax1 = plt.subplots(figsize=(7, 5))
fig2.suptitle("StrongArm — Tcmp and τ vs. Tail Width (M0)\n"
              "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV", fontsize=12)

color_tcmp = "#1f77b4"
color_tau  = "#d62728"

l1, = ax1.plot(valid_w, valid_tcmp, "o-", color=color_tcmp, lw=2.2,
               ms=8, mfc="white", mew=2.5, label="Tcmp (ps)")
ax1.set_xlabel("W_tail / µm", fontsize=11)
ax1.set_ylabel("Tcmp (ps)", color=color_tcmp, fontsize=11)
ax1.tick_params(axis="y", labelcolor=color_tcmp, labelsize=10)
ax1.set_xlim(0.5, 10.5)
ax1.set_ylim(bottom=0)
ax1.set_xticks(W_RANGE)
ax1.grid(True, linestyle="--", alpha=0.35)

ax2 = ax1.twinx()
if valid_w_t:
    l2, = ax2.plot(valid_w_t, valid_tau, "s--", color=color_tau, lw=1.8,
                   ms=7, mfc="white", mew=2.2, label="τ (ps)")
    ax2.set_ylabel("τ (ps)", color=color_tau, fontsize=11)
    ax2.tick_params(axis="y", labelcolor=color_tau, labelsize=10)
    ax2.set_ylim(bottom=0)
    lines = [l1, l2]
else:
    lines = [l1]

ax1.set_title("Tail switch M0: Tcmp and latch τ vs. width", fontsize=10)
ax1.legend(lines, [l.get_label() for l in lines], fontsize=9, loc="upper right")

plt.tight_layout()
out2 = OUTPUT_DIR / "tcmp_tau_vs_tail_width.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {out2}")

# ── Figure 3: Delta Tcmp (improvement relative to W=1) ──────────────────────
if len(valid_w) > 1:
    tcmp_1um = valid_tcmp[0]  # Tcmp at W=1µm
    delta_pct = [(tcmp_1um - t) / tcmp_1um * 100 for t in valid_tcmp]

    fig3, ax3 = plt.subplots(figsize=(7, 4.5))
    fig3.suptitle("Tcmp improvement relative to W_tail=1 µm\n"
                  "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz", fontsize=12)

    ax3.bar(valid_w, delta_pct, color="#2ca02c", alpha=0.75, edgecolor="black", lw=0.8)
    ax3.axhline(0, color="black", lw=0.8)
    ax3.set_xlabel("W_tail / µm", fontsize=11)
    ax3.set_ylabel("Tcmp reduction (%)", fontsize=11)
    ax3.set_xticks(W_RANGE)
    ax3.set_title("Diminishing returns as W_tail increases", fontsize=10)
    ax3.grid(True, axis="y", linestyle="--", alpha=0.45)
    ax3.tick_params(labelsize=10)

    plt.tight_layout()
    out3 = OUTPUT_DIR / "tcmp_improvement_vs_tail_width.png"
    fig3.savefig(out3, dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print(f"Saved: {out3}")

print("\nDone.")
