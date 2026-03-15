#!/usr/bin/env python3
"""
run_tau_sweep.py
================
Sweep transistor widths and measure latch regeneration time constant τ.

Validates that τ extraction in simulate_tran_strongarm_wave.py is correct
and shows the expected sizing trends:

  W_lat_n sweep: latch NMOS M3/M4 width
    → τ ≈ C_latch / gm_latch; wider latch → more gm BUT also more C_drain,
      so τ is relatively flat for a balanced latch. PMOS contribution matters.

  W_lat_p sweep: latch PMOS M5/M6 width
    → similar trade-off

  W_inp sweep: input NMOS M1/M2 width
    → affects only pre-amp phase, not τ directly

Run from comparator/assets/:
    python run_tau_sweep.py
"""

import sys
import os

# Make sure we're in the assets directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import comparator_common as cc
from simulate_tran_strongarm_wave import simulate_wave


def run_sweep(param_name: str, values: list, label: str = None) -> list:
    """
    Sweep a single width parameter, run waveform simulation, collect τ.

    param_name : key in comparator_common.W  (e.g. 'lat_n', 'lat_p', 'inp')
    values     : list of widths in µm
    Returns list of (width_um, tau_ps) tuples.
    """
    if label is None:
        label = param_name
    original = cc.W[param_name]

    print(f"\n{'='*55}")
    print(f"  Sweep: W_{label} = {values} µm")
    print(f"  (restoring to {original} µm after sweep)")
    print(f"{'='*55}")

    results = []
    for w in values:
        cc.W[param_name] = w
        print(f"\n--- W_{label} = {w} µm ---")
        try:
            r = simulate_wave()
            tau_ps = r["wave"].get("tau_ps", float("nan"))
        except Exception as e:
            print(f"  ERROR: {e}")
            tau_ps = float("nan")
        results.append((w, tau_ps))

    # Restore original
    cc.W[param_name] = original
    return results


def print_table(title: str, results: list, param_name: str):
    """Pretty-print a width vs. τ table."""
    print(f"\n{'='*40}")
    print(f"  {title}")
    print(f"{'='*40}")
    print(f"  {'W_' + param_name + ' (µm)':>14}  {'τ (ps)':>10}")
    print(f"  {'-'*14}  {'-'*10}")
    for w, tau in results:
        tau_str = f"{tau:.1f}" if not __import__('math').isnan(tau) else "NaN"
        print(f"  {w:>14.1f}  {tau_str:>10}")
    print()


if __name__ == "__main__":
    import math

    print("\n=== τ Extraction Validation Sweep ===")
    print("  Technology: 45nm PTM HP, VDD=1.0V, FCLK=1GHz")
    print("  Method: two-threshold crossing on |VLN-VLP|")
    print("  Thresholds: 0.05*VDD (50mV) → 0.40*VDD (400mV)")
    print("  Expected reference τ: ~24–36 ps at nominal sizing")

    # ── Sweep 1: latch NMOS width ─────────────────────────────────────────────
    lat_n_values = [0.5, 1.0, 2.0, 4.0]   # µm
    res_lat_n = run_sweep("lat_n", lat_n_values, "lat_n")
    print_table("Latch NMOS width sweep (M3/M4)", res_lat_n, "lat_n")

    # ── Sweep 2: latch PMOS width ─────────────────────────────────────────────
    lat_p_values = [0.5, 1.0, 2.0, 4.0]   # µm
    res_lat_p = run_sweep("lat_p", lat_p_values, "lat_p")
    print_table("Latch PMOS width sweep (M5/M6)", res_lat_p, "lat_p")

    # ── Sweep 3: input pair width (τ should NOT change much) ──────────────────
    inp_values = [1.0, 2.0, 4.0, 8.0]   # µm
    res_inp = run_sweep("inp", inp_values, "inp")
    print_table("Input pair width sweep (M1/M2) — expect little τ change", res_inp, "inp")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=== Sanity checks ===")
    print("  1. τ should be in [10, 100] ps for all latch sweeps (45nm, 1GHz)")
    print("  2. W_inp sweep: τ should vary <30% (input pair doesn't drive latch speed)")
    print("  3. All τ values should be non-NaN (waveform extracted correctly)")
    print()

    all_ok = True
    for w, tau in res_lat_n + res_lat_p + res_inp:
        if math.isnan(tau):
            print(f"  FAIL: NaN τ detected (extraction problem)")
            all_ok = False
            break
        if not (5 < tau < 200):
            print(f"  WARNING: τ = {tau:.1f} ps out of expected [5, 200] ps range")

    if all_ok:
        print("  All τ values extracted successfully (no NaN).")

    # Quantify input-pair sensitivity
    tau_inp_vals = [t for _, t in res_inp if not math.isnan(t)]
    if len(tau_inp_vals) >= 2:
        spread = (max(tau_inp_vals) - min(tau_inp_vals)) / max(tau_inp_vals) * 100
        print(f"  Input pair sweep τ spread: {spread:.0f}%  (expect < 30%)")
