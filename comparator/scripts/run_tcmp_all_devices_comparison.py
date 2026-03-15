#!/usr/bin/env python3
"""
run_tcmp_all_devices_comparison.py
====================================
Sweep W for all four transistor groups (tail / input pair / latch NMOS /
latch PMOS) and plot all four Tcmp curves on a single axes for direct
sensitivity comparison.

Outputs saved to:
  H:/analog-circuit-skills/comparator-workspace/iteration-1/
      tcmp-all-devices-comparison/without_skill/outputs/

Run from comparator/scripts/:
    python run_tcmp_all_devices_comparison.py
"""

import os, math, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# ── chdir so relative imports inside comparator_common work correctly ──────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from comparator_common import compute_tcmp, TCLK
from simulate_tran_strongarm_wave import simulate_wave, WAVE_NCYC

# ── Output directory ───────────────────────────────────────────────────────────
OUT_DIR = Path(
    "H:/analog-circuit-skills/comparator-workspace/iteration-1/"
    "tcmp-all-devices-comparison/without_skill/outputs"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Sweep range ────────────────────────────────────────────────────────────────
W_RANGE = list(range(1, 11))   # 1–10 µm, step 1 µm

# Nominal widths for reference markers
NOMINAL = {
    "tail":  cc.W["tail"],
    "inp":   cc.W["inp"],
    "lat_n": cc.W["lat_n"],
    "lat_p": cc.W["lat_p"],
}

# ── Per-device sweep ───────────────────────────────────────────────────────────
def run_sweep(param_name, values):
    """Sweep one transistor width; return list of (W_um, Tcmp_ps)."""
    original = cc.W[param_name]
    results = []
    for w in values:
        cc.W[param_name] = w
        print(f"  W_{param_name} = {w} um ...", end="  ", flush=True)
        tcmp = float("nan")
        try:
            r = simulate_wave()
            wv = r["wave"]
            if wv["time"] is not None and wv["outp"] is not None:
                tcmp = compute_tcmp(wv["time"], wv["outp"], WAVE_NCYC)
        except Exception as e:
            print(f"ERROR: {e}")
        print(f"Tcmp={tcmp:.1f} ps" if not math.isnan(tcmp) else "Tcmp=NaN")
        results.append((w, tcmp))
    cc.W[param_name] = original
    return results


sweeps_cfg = [
    ("tail",  "Tail NMOS M0"),
    ("inp",   "Input pair NMOS M1/M2"),
    ("lat_n", "Latch NMOS M3/M4"),
    ("lat_p", "Latch PMOS M5/M6"),
]

data = {}
sensitivity = {}  # dTcmp/dW (ps/um) — slope from linear fit over valid points

for key, label in sweeps_cfg:
    print(f"\n=== Sweep W_{key} ===")
    data[key] = run_sweep(key, W_RANGE)

    ws   = [r[0] for r in data[key]]
    tcmp = [r[1] for r in data[key]]
    vw   = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
    vt   = [t for t in tcmp if not math.isnan(t)]

    if len(vw) >= 2:
        slope, _ = np.polyfit(vw, vt, 1)   # ps per um
        sensitivity[key] = slope
    else:
        sensitivity[key] = float("nan")

# ── Figure: all four Tcmp curves on one axes ──────────────────────────────────
colors  = {"tail": "#1f77b4", "inp": "#2ca02c", "lat_n": "#d62728", "lat_p": "#9467bd"}
markers = {"tail": "o",       "inp": "^",        "lat_n": "s",        "lat_p": "D"}
labels  = {
    "tail":  "Tail NMOS M0",
    "inp":   "Input pair NMOS M1/M2",
    "lat_n": "Latch NMOS M3/M4",
    "lat_p": "Latch PMOS M5/M6",
}

fig, ax = plt.subplots(figsize=(8, 5.5))
fig.suptitle(
    "StrongArm Comparator — Tcmp Sensitivity to Transistor Width\n"
    "45 nm PTM HP, VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV",
    fontsize=11,
)

for key, _ in sweeps_cfg:
    res  = data[key]
    ws   = [r[0] for r in res]
    tcmp = [r[1] for r in res]
    vw   = [w for w, t in zip(ws, tcmp) if not math.isnan(t)]
    vt   = [t for t in tcmp if not math.isnan(t)]

    slp = sensitivity[key]
    lbl = f"{labels[key]}  (slope {slp:+.1f} ps/um)"

    ax.plot(vw, vt,
            markers[key] + "-",
            color=colors[key],
            lw=2, ms=7, mfc="white", mew=2,
            label=lbl,
            zorder=3)

    # Mark nominal operating point
    nom_w = NOMINAL[key]
    nom_t = next((t for w, t in res if w == nom_w and not math.isnan(t)), None)
    if nom_t is not None:
        ax.plot(nom_w, nom_t,
                markers[key],
                color=colors[key],
                ms=11, mfc=colors[key], mew=2,
                zorder=4)

ax.set_xlabel("Transistor Width (um)", fontsize=11)
ax.set_ylabel("Tcmp (ps)", fontsize=11)
ax.set_title("All devices — Tcmp vs. Width (sensitivity comparison)", fontsize=10)
ax.set_xlim(0.5, 10.5)
ax.set_ylim(bottom=0)
ax.grid(True, linestyle="--", alpha=0.45)
ax.legend(fontsize=8.5, loc="best")
ax.tick_params(labelsize=9)

# Annotate most sensitive device
most_sensitive = max(
    (k for k in sensitivity if not math.isnan(sensitivity[k])),
    key=lambda k: abs(sensitivity[k])
)
ax.text(
    0.98, 0.97,
    f"Most sensitive: {labels[most_sensitive]}\n"
    f"  slope = {sensitivity[most_sensitive]:+.1f} ps/um",
    transform=ax.transAxes,
    ha="right", va="top",
    fontsize=8,
    bbox=dict(boxstyle="round,pad=0.4", fc="lightyellow", ec="gray", alpha=0.85),
)

plt.tight_layout()
out_png = OUT_DIR / "tcmp_all_devices_comparison.png"
fig.savefig(out_png, dpi=150, bbox_inches="tight")
print(f"\nSaved: {out_png}")
plt.close(fig)


# ── Print sensitivity table ────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("Tcmp Sensitivity Summary  (linear slope over 1–10 um)")
print("=" * 55)
ranked = sorted(
    [(k, sensitivity[k]) for k in sensitivity if not math.isnan(sensitivity[k])],
    key=lambda x: abs(x[1]),
    reverse=True,
)
for rank, (k, slp) in enumerate(ranked, 1):
    print(f"  #{rank}  {labels[k]:<30s}  {slp:+.2f} ps/um")
print("=" * 55)


# ── Write summary.txt ──────────────────────────────────────────────────────────
summary_lines = [
    "Tcmp vs. Transistor Width — All Devices Comparison",
    "====================================================",
    "",
    "Circuit: StrongArm dynamic comparator",
    "Technology: 45 nm PTM HP",
    "Conditions: VDD=1.0 V, FCLK=1 GHz, Vin=+1 mV (differential)",
    f"Width sweep: {W_RANGE[0]}–{W_RANGE[-1]} um, step 1 um",
    "",
    "Nominal widths:",
    f"  tail  = {NOMINAL['tail']:.1f} um",
    f"  inp   = {NOMINAL['inp']:.1f} um",
    f"  lat_n = {NOMINAL['lat_n']:.1f} um",
    f"  lat_p = {NOMINAL['lat_p']:.1f} um",
    "",
    "Tcmp sensitivity (linear slope dTcmp/dW) — ranked most to least sensitive:",
]
for rank, (k, slp) in enumerate(ranked, 1):
    direction = "increases" if slp > 0 else "decreases"
    summary_lines.append(
        f"  #{rank}  {labels[k]:<30s}  {slp:+.2f} ps/um  "
        f"(Tcmp {direction} as W grows)"
    )

summary_lines += [
    "",
    f"Most sensitive transistor: {labels[most_sensitive]}",
    f"  Widening this device has the largest per-micron effect on Tcmp.",
    "",
    "Physical interpretation:",
    "  - Tail NMOS (M0): controls charge-up time of VX nodes; wider -> faster",
    "    pre-charge -> smaller Tcmp (negative slope expected).",
    "  - Input pair (M1/M2): drives initial VX voltage step proportional to",
    "    Vin; wider -> larger gm -> faster kick -> smaller Tcmp.",
    "  - Latch NMOS (M3/M4): set regeneration bandwidth; wider -> smaller tau",
    "    -> faster decision -> smaller Tcmp.",
    "  - Latch PMOS (M5/M6): provide cross-coupled regeneration (opposite",
    "    polarity to NMOS); wider -> stronger pull-up can slow NMOS latch",
    "    (competing effect); sensitivity typically smaller.",
    "",
    f"Output PNG: {out_png}",
]

summary_path = OUT_DIR / "summary.txt"
summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
print(f"Saved: {summary_path}")
print("\nDone.")
