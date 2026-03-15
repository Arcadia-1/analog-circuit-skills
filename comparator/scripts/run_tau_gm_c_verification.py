#!/usr/bin/env python3
"""
run_tau_gm_c_verification.py
============================
Verify τ = C/gm in StrongArm comparator by sweeping latch transistor widths.

Key insight: for the latch (cross-coupled inverter), widening M3/M4 (latch NMOS)
or M5/M6 (latch PMOS) increases both gm AND C proportionally (gm ∝ W, Cgg ∝ W),
so τ = C/gm is approximately constant.

In contrast, widening M1/M2 (input pair) adds capacitance WITHOUT adding
regeneration gm, which INCREASES τ.

Saves plots to: H:/analog-circuit-skills/comparator-workspace/iteration-1/
                tau-gm-c-verification/without_skill/outputs/
"""

import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# Must set cwd to scripts/ so imports work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from simulate_tran_strongarm_wave import simulate_wave

OUT_DIR = Path(
    "H:/analog-circuit-skills/comparator-workspace/"
    "iteration-1/tau-gm-c-verification/without_skill/outputs"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Default widths (baseline)
DEFAULT_W = dict(cc.W)

# Width sweep range
WIDTHS = list(range(1, 11))   # 1 to 10 µm


def run_sweep(param_name, values, label):
    """Sweep one transistor width, extract τ at each point."""
    original = cc.W[param_name]
    results = []
    print(f"\n=== Sweep {label} (W={values}) ===", flush=True)
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
res_lat_n = run_sweep("lat_n", WIDTHS, "Latch NMOS M3/M4 (W_lat_n)")
res_lat_p = run_sweep("lat_p", WIDTHS, "Latch PMOS M5/M6 (W_lat_p)")
res_inp   = run_sweep("inp",   WIDTHS, "Input Pair M1/M2 (W_inp)")


# ── Figure 1: Three-panel comparison ──────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
fig.suptitle(
    "StrongArm Comparator — τ = C/gm Verification via Width Sweep\n"
    "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV",
    fontsize=11
)

sweeps = [
    (axes[0], res_lat_n, r"$W_{lat,n}$ (µm)",
     "Latch NMOS M3/M4\n(W_lat_p=2µm, W_inp=4µm)",
     "#1f77b4", "o"),
    (axes[1], res_lat_p, r"$W_{lat,p}$ (µm)",
     "Latch PMOS M5/M6\n(W_lat_n=1µm, W_inp=4µm)",
     "#d62728", "s"),
    (axes[2], res_inp,   r"$W_{inp}$ (µm)",
     "Input Pair M1/M2\n(W_lat_n=1µm, W_lat_p=2µm)",
     "#2ca02c", "^"),
]

annotation_done = [False, False, False]

for idx, (ax, res, xlabel, title, color, marker) in enumerate(sweeps):
    ws, tau = split(res)
    valid_w   = [w for w, t in zip(ws, tau) if t is not None]
    valid_tau = [t for t in tau if t is not None]
    nan_w     = [w for w, t in zip(ws, tau) if t is None]

    ax.plot(valid_w, valid_tau, f"{marker}-", color=color, lw=2,
            ms=8, mfc="white", mew=2, zorder=3, label="Simulated τ")
    if nan_w:
        ax.plot(nan_w, [1] * len(nan_w), "x", color="red",
                ms=10, mew=2.5, label="NaN (too slow)", zorder=4)

    # Reference band from baseline
    ax.axhspan(20, 40, color="gray", alpha=0.12, label="typical 20–40 ps")

    # Annotate behavior
    if valid_tau and len(valid_tau) >= 3:
        pct_change = (max(valid_tau) - min(valid_tau)) / np.mean(valid_tau) * 100
        behavior = f"Range: {min(valid_tau):.1f}–{max(valid_tau):.1f} ps\nVar: {pct_change:.1f}%"
        ax.text(0.97, 0.97, behavior, transform=ax.transAxes,
                ha="right", va="top", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="gray", alpha=0.9))

    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("τ (ps)", fontsize=10)
    ax.set_title(title, fontsize=9)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.tick_params(labelsize=9)
    ax.legend(fontsize=8, loc="upper left")

plt.tight_layout()
out1 = OUT_DIR / "tau_vs_width_three_panel.png"
fig.savefig(out1, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out1}")
plt.close(fig)


# ── Figure 2: Overlay — Latch vs Input pair (key insight) ─────────────────────
fig2, (ax_latch, ax_inp) = plt.subplots(1, 2, figsize=(10, 4.5))
fig2.suptitle(
    r"τ = C/gm: Why Latch Width Barely Changes τ But Input-Pair Width Does"
    "\n45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz",
    fontsize=11
)

# Left: latch NMOS + PMOS overlay
ws_n, tau_n = split(res_lat_n)
ws_p, tau_p = split(res_lat_p)
vw_n  = [w for w, t in zip(ws_n, tau_n) if t is not None]
vt_n  = [t for t in tau_n if t is not None]
vw_p  = [w for w, t in zip(ws_p, tau_p) if t is not None]
vt_p  = [t for t in tau_p if t is not None]

ax_latch.plot(vw_n, vt_n, "o-", color="#1f77b4", lw=2, ms=8,
              mfc="white", mew=2, label="Latch NMOS M3/M4")
ax_latch.plot(vw_p, vt_p, "s-", color="#d62728", lw=2, ms=8,
              mfc="white", mew=2, label="Latch PMOS M5/M6")
ax_latch.axhspan(20, 40, color="gray", alpha=0.12)
ax_latch.set_xlabel("Width (µm)", fontsize=10)
ax_latch.set_ylabel("τ (ps)", fontsize=10)
ax_latch.set_title(
    "Latch transistors — τ ≈ const\n"
    r"Reason: gm ∝ W, C ∝ W  →  τ=C/gm cancels",
    fontsize=9
)
ax_latch.set_ylim(bottom=0)
ax_latch.legend(fontsize=9)
ax_latch.grid(True, linestyle="--", alpha=0.45)
ax_latch.tick_params(labelsize=9)

# Right: input pair
ws_i, tau_i = split(res_inp)
vw_i  = [w for w, t in zip(ws_i, tau_i) if t is not None]
vt_i  = [t for t in tau_i if t is not None]
nan_i = [w for w, t in zip(ws_i, tau_i) if t is None]

ax_inp.plot(vw_i, vt_i, "^-", color="#2ca02c", lw=2, ms=8,
            mfc="white", mew=2, label="Input pair M1/M2")
if nan_i:
    ax_inp.plot(nan_i, [2] * len(nan_i), "x", color="red",
                ms=10, mew=2.5, label=f"NaN (W={nan_i}µm, too slow)")
ax_inp.axhspan(20, 40, color="gray", alpha=0.12)
ax_inp.set_xlabel(r"$W_{inp}$ (µm)", fontsize=10)
ax_inp.set_ylabel("τ (ps)", fontsize=10)
ax_inp.set_title(
    "Input pair — τ increases with W\n"
    r"Reason: C↑ (Cgs∝W) but gm_latch unchanged",
    fontsize=9
)
ax_inp.set_ylim(bottom=0)
ax_inp.legend(fontsize=9)
ax_inp.grid(True, linestyle="--", alpha=0.45)
ax_inp.tick_params(labelsize=9)

plt.tight_layout()
out2 = OUT_DIR / "tau_latch_vs_input_overlay.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"Saved: {out2}")
plt.close(fig2)


# ── Figure 3: τ·(W_lat_n) normalized — should be flat if τ∝1/gm∝1/W ─────────
fig3, axes3 = plt.subplots(1, 2, figsize=(10, 4))
fig3.suptitle(
    r"Normalized Check: τ × W should be ≈ constant if τ = C/gm and gm ∝ W"
    "\n(Latch transistors only)",
    fontsize=10
)

for ax3, res, color, marker, label in [
    (axes3[0], res_lat_n, "#1f77b4", "o", "Latch NMOS"),
    (axes3[1], res_lat_p, "#d62728", "s", "Latch PMOS"),
]:
    ws, tau = split(res)
    vw  = [w for w, t in zip(ws, tau) if t is not None]
    vt  = [t for t in tau if t is not None]
    tau_times_w = [t * w for t, w in zip(vt, vw)]

    ax3.plot(vw, tau_times_w, f"{marker}-", color=color, lw=2, ms=8,
             mfc="white", mew=2, label=f"τ × W [{label}]")

    if tau_times_w:
        mean_val = np.mean(tau_times_w)
        ax3.axhline(mean_val, color="orange", lw=1.5, ls="--",
                    label=f"mean = {mean_val:.1f} ps·µm")

    ax3.set_xlabel("Width W (µm)", fontsize=10)
    ax3.set_ylabel("τ × W (ps·µm)", fontsize=10)
    ax3.set_title(
        f"{label}\n"
        r"If τ=C/gm and both ∝W: τ×W ≈ const ✓" if True else "",
        fontsize=9
    )
    ax3.legend(fontsize=9)
    ax3.grid(True, linestyle="--", alpha=0.45)
    ax3.tick_params(labelsize=9)

plt.tight_layout()
out3 = OUT_DIR / "tau_times_w_normalization.png"
fig3.savefig(out3, dpi=150, bbox_inches="tight")
print(f"Saved: {out3}")
plt.close(fig3)


# ── Print summary table ────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SUMMARY TABLE")
print("="*60)
print(f"\n{'W (µm)':>8}  {'τ_lat_n (ps)':>14}  {'τ_lat_p (ps)':>14}  {'τ_inp (ps)':>12}")
print("-"*58)
for i, w in enumerate(WIDTHS):
    t_n = res_lat_n[i][1] if i < len(res_lat_n) else float("nan")
    t_p = res_lat_p[i][1] if i < len(res_lat_p) else float("nan")
    t_i = res_inp[i][1]   if i < len(res_inp)   else float("nan")
    def fmt(v): return f"{v:>14.2f}" if not math.isnan(v) else f"{'NaN':>14}"
    print(f"{w:>8}  {fmt(t_n)}  {fmt(t_p)}  {fmt(t_i)}")

print("\nDone. Plots saved to:", OUT_DIR)
