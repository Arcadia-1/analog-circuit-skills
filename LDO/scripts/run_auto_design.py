#!/usr/bin/env python3
"""
run_auto_design.py
==================
Automatic LDO transistor-level design tool.

Given user specs (VOUT, VIN, ILOAD_max), automatically:
  1. Computes feedback divider (R_FB_TOP / R_FB_BOT) for the target VOUT
  2. Scales pass transistor M2 for ILOAD_max
  3. Adjusts compensation network (R_COMP, C_COMP) to place fz at target fraction of GBW
  4. Runs verification simulations and reports metrics

Design equations
----------------
  VOUT  = VREF * (R_FB_TOP + R_FB_BOT) / R_FB_BOT
      → R_FB_TOP = R_FB_BOT * (VOUT / VREF - 1)

  M2 total_W scales linearly with ILOAD (empirical, from reference 100 mA / 12000 um):
      W_M2_total = 12000 um * (ILOAD_ma / 100)
      m_M2 = round(W_M2_total / W_per_finger)   [W_per_finger = 120 um]

  fz = 1 / (2*pi * R_COMP * C_COMP)
      → C_COMP = 1 / (2*pi * fz_target * R_COMP)
      where fz_target = fz_fraction * GBW_target  (default fz_fraction = 0.4)

Limitations
-----------
  - VIN change only affects the DUT subcircuit; AC/DC testbenches still use
    VIN_NOM = 2.3 V from ldo_common at import time. For VIN != 2.3 V the
    simulation bias point differs slightly, but VOUT regulation and loop-gain
    metrics remain valid as long as VIN > VOUT + 0.5 V dropout.
  - Error-amp transistors (M0/M1/M3/M4/M5/M6) are NOT auto-scaled here;
    their W/L are unchanged from the reference design. If IBIAS or diff-pair
    sizing matters, edit ldo_common.py globals directly and re-run.

Usage
-----
  cd LDO/scripts/

  # Same output voltage (1.8 V), different load:
  python run_auto_design.py --vout 1.8 --vin 2.3 --iload 50

  # Different output voltage:
  python run_auto_design.py --vout 1.2 --vin 1.8 --iload 100

  # High-current design:
  python run_auto_design.py --vout 3.3 --vin 5.0 --iload 500 --gbw 2000

  # Design only, no simulation:
  python run_auto_design.py --vout 2.5 --vin 3.3 --iload 200 --no-sim

Arguments
---------
  --vout   VOUT   Target output voltage (V)         [default: 1.8]
  --vin    VIN    Input supply voltage (V)           [default: 2.3]
  --iload  ILOAD  Maximum load current (mA)          [default: 100]
  --vref   VREF   Reference voltage (V)              [default: 0.9]
  --gbw    GBW    Target GBW (kHz)                   [default: 1284]
  --fz-frac FRAC  fz / GBW ratio for PM (0.3-0.6)   [default: 0.4]
  --no-sim        Skip simulation, print design only

Output
------
  WORK/logs/ldo_auto_design.txt
"""

import argparse
import sys
import os
import math

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

import ldo_common as ldo
from simulate_ldo_ac import simulate_ac
from ngspice_common import LOG_DIR

# ── Reference design point (100 mA, VOUT=1.8 V, PTM 180nm) ─────────────
_REF_ILOAD_MA      = 100.0     # mA
_REF_W_PER_FINGER  = 120.0     # um  (W_M2_UM baseline)
_REF_M_M2          = 100       # fingers at 100 mA
_REF_RCOMP         = 2000.0    # Ω


# ═══════════════════════════════════════════════════════════════════════════════
#  Design calculation
# ═══════════════════════════════════════════════════════════════════════════════

def design(vout, vin, iload_ma, vref, gbw_khz, fz_frac):
    """
    Compute circuit parameters for the given specs.

    Returns dict with all designed values (does NOT modify ldo_common).
    """
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  LDO Auto-Design")
    print(f"  Specs: VOUT={vout} V  VIN={vin} V  ILOAD={iload_ma} mA")
    print(f"         Target GBW={gbw_khz} kHz  fz/GBW={fz_frac:.2f}")
    print(sep)

    # ── Dropout check ──────────────────────────────────────────────────────────
    V_DROPOUT_MIN = 0.45     # V  estimated from reference (VIN - VOUT = 0.5 V)
    if vin < vout + V_DROPOUT_MIN:
        raise ValueError(
            f"VIN={vin} V is too low — need at least "
            f"VOUT + {V_DROPOUT_MIN} V = {vout + V_DROPOUT_MIN:.2f} V"
        )

    # ── VREF check ─────────────────────────────────────────────────────────────
    if vref >= vout:
        raise ValueError(f"VREF={vref} V must be < VOUT={vout} V")

    # ── 1. Feedback divider ────────────────────────────────────────────────────
    r_fb_bot = float(ldo.R_FB_BOT)          # keep bottom resistor unchanged
    r_fb_top_exact = r_fb_bot * (vout / vref - 1.0)
    r_fb_top = round(r_fb_top_exact / 10) * 10   # round to nearest 10 Ω
    beta     = r_fb_bot / (r_fb_top + r_fb_bot)
    vout_act = vref / beta

    print(f"\n  [1] Feedback divider")
    print(f"      R_FB_BOT  = {r_fb_bot:.0f} Ohm  (unchanged)")
    print(f"      R_FB_TOP  = {r_fb_top:.0f} Ohm  (exact: {r_fb_top_exact:.1f} Ohm)")
    print(f"      beta      = {beta:.5f}")
    print(f"      VOUT_act  = {vout_act:.4f} V  (error: {(vout_act-vout)*1e3:+.1f} mV)")

    # ── 2. Pass transistor M2 sizing ──────────────────────────────────────────
    # Empirical: scale total W linearly with ILOAD relative to reference design.
    # Reference: 100 mA → total W = 120 um × 100 = 12000 um.
    w_total_ref = _REF_W_PER_FINGER * _REF_M_M2    # 12000 um
    w_total_new = w_total_ref * (iload_ma / _REF_ILOAD_MA)
    w_per_finger = _REF_W_PER_FINGER                # keep 120 um per finger
    m_m2 = max(1, round(w_total_new / w_per_finger))
    w_total_act = w_per_finger * m_m2

    print(f"\n  [2] Pass transistor M2  (PMOS, L={ldo.L_M2_NM} nm)")
    print(f"      W_total_target = {w_total_new:.0f} um")
    print(f"      W_per_finger   = {w_per_finger:.0f} um  -->  m = {m_m2}")
    print(f"      W_total_actual = {w_total_act:.0f} um"
          f"  (ILOAD ratio: {w_total_act/w_total_ref*100:.0f}%)")

    # ── 3. Compensation network ────────────────────────────────────────────────
    # Target: fz = fz_frac × GBW  for adequate phase lead.
    # Keep R_COMP = 2000 Ω; compute C_COMP.
    r_comp   = _REF_RCOMP
    fz_hz    = fz_frac * gbw_khz * 1e3
    c_comp   = 1.0 / (2 * math.pi * fz_hz * r_comp)
    c_comp_pf = c_comp * 1e12

    # Round to nearest E12 value
    c_comp_std_pf = _nearest_e12_pf(c_comp_pf)
    c_comp_std    = c_comp_std_pf * 1e-12
    fz_act        = 1.0 / (2 * math.pi * r_comp * c_comp_std)

    print(f"\n  [3] Compensation network")
    print(f"      GBW_target  = {gbw_khz:.0f} kHz")
    print(f"      fz_target   = {fz_hz/1e3:.1f} kHz  (= {fz_frac:.2f} x GBW)")
    print(f"      R_COMP      = {r_comp:.0f} Ohm  (fixed)")
    print(f"      C_COMP_calc = {c_comp_pf:.1f} pF")
    print(f"      C_COMP_std  = {c_comp_std_pf:.1f} pF  (E12 rounded)")
    print(f"      fz_actual   = {fz_act/1e3:.1f} kHz")

    # ── 4. Load resistor for VOUT ─────────────────────────────────────────────
    r_load = vout / (iload_ma * 1e-3)
    print(f"\n  [4] Load  (for simulation)")
    print(f"      R_LOAD = VOUT/ILOAD = {vout:.1f}/{iload_ma:.0f}mA"
          f" = {r_load:.1f} Ohm")

    return dict(
        vout_target  = vout,
        vin          = vin,
        vref         = vref,
        iload_ma     = iload_ma,
        r_fb_top     = r_fb_top,
        r_fb_bot     = r_fb_bot,
        beta         = beta,
        vout_act     = vout_act,
        m_m2         = m_m2,
        w_m2_um      = w_per_finger,
        w_m2_total   = w_total_act,
        r_comp       = r_comp,
        c_comp       = c_comp_std,
        c_comp_pf    = c_comp_std_pf,
        fz_hz        = fz_act,
        gbw_khz      = gbw_khz,
        r_load       = r_load,
    )


def _nearest_e12_pf(c_pf):
    """Round a capacitance in pF to the nearest E12 series value."""
    e12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
    if c_pf <= 0:
        return 1.0
    decade  = 10 ** math.floor(math.log10(c_pf))
    mantissa = c_pf / decade
    best = min(e12, key=lambda v: abs(v - mantissa))
    return best * decade


# ═══════════════════════════════════════════════════════════════════════════════
#  Apply design + verify by simulation
# ═══════════════════════════════════════════════════════════════════════════════

def apply_design(params):
    """Write designed values into ldo_common module globals."""
    ldo.VIN_NOM  = params["vin"]
    ldo.VOUT_NOM = params["vout_target"]
    ldo.VREF_NOM = params["vref"]
    ldo.R_FB_TOP = params["r_fb_top"]
    ldo.R_FB_BOT = params["r_fb_bot"]
    ldo.R_COMP   = params["r_comp"]
    ldo.C_COMP   = params["c_comp"]
    ldo.W_M2_UM  = params["w_m2_um"]
    ldo.M_M2     = params["m_m2"]
    # Update load for correct bias
    ldo.R_LOAD_DEFAULT = round(params["r_load"])


def verify(params):
    """
    Run AC verification (loop gain, PSRR, Zout).
    Returns metrics dict.
    """
    print("\n  Running AC verification ...")
    apply_design(params)
    res = simulate_ac()
    m   = res.get("metrics", {})
    gbw_sim  = m.get("gbw_hz",           float("nan"))
    pm_sim   = m.get("phase_margin_deg", float("nan"))
    dc_gain  = m.get("dc_gain_db",       float("nan"))
    psrr_dc  = m.get("psrr_dc_db",       float("nan"))

    print(f"\n  AC results:")
    print(f"    GBW      = {gbw_sim/1e3:.1f} kHz  (target {params['gbw_khz']:.0f} kHz)")
    print(f"    PM       = {pm_sim:.1f} deg")
    print(f"    DC gain  = {dc_gain:.1f} dB")
    print(f"    PSRR_DC  = {psrr_dc:.1f} dB")
    return {"gbw_hz": gbw_sim, "pm_deg": pm_sim,
            "dc_gain_db": dc_gain, "psrr_dc_db": psrr_dc}


# ═══════════════════════════════════════════════════════════════════════════════
#  Report
# ═══════════════════════════════════════════════════════════════════════════════

def _build_report(params, sim_metrics):
    lines = [
        "=" * 60,
        "  LDO Auto-Design Report",
        "=" * 60,
        "",
        "  Specifications",
        f"    VOUT_target = {params['vout_target']:.3f} V",
        f"    VIN         = {params['vin']:.3f} V",
        f"    ILOAD_max   = {params['iload_ma']:.0f} mA",
        f"    VREF        = {params['vref']:.3f} V",
        "",
        "  Designed Parameters",
        f"    R_FB_TOP = {params['r_fb_top']:.0f} Ohm",
        f"    R_FB_BOT = {params['r_fb_bot']:.0f} Ohm",
        f"    beta     = {params['beta']:.5f}",
        f"    VOUT_act = {params['vout_act']:.4f} V  "
        f"(error {(params['vout_act']-params['vout_target'])*1e3:+.1f} mV)",
        "",
        f"    M2: W = {params['w_m2_um']:.0f} um x m = {params['m_m2']}",
        f"        W_total = {params['w_m2_total']:.0f} um  "
        f"L = {ldo.L_M2_NM} nm",
        "",
        f"    R_COMP   = {params['r_comp']:.0f} Ohm",
        f"    C_COMP   = {params['c_comp_pf']:.1f} pF",
        f"    fz_act   = {params['fz_hz']/1e3:.1f} kHz",
        f"    R_LOAD   = {params['r_load']:.1f} Ohm  "
        f"({params['iload_ma']:.0f} mA full load)",
    ]

    if sim_metrics:
        gbw = sim_metrics.get("gbw_hz", float("nan"))
        pm  = sim_metrics.get("pm_deg",  float("nan"))
        dc  = sim_metrics.get("dc_gain_db",  float("nan"))
        psr = sim_metrics.get("psrr_dc_db",  float("nan"))
        lines += [
            "",
            "  Simulation Verification (AC)",
            f"    GBW      = {gbw/1e3:.1f} kHz  (target {params['gbw_khz']:.0f} kHz)",
            f"    PM       = {pm:.1f} deg",
            f"    DC gain  = {dc:.1f} dB",
            f"    PSRR_DC  = {psr:.1f} dB",
        ]
        pm_ok = pm >= 45
        lines.append("")
        lines.append(f"  STATUS: {'PASS' if pm_ok else 'WARN (PM < 45 deg)'}")
        if not pm_ok:
            lines.append("  TIP: increase C_COMP (lower fz) or reduce R_COMP.")

    lines += [
        "",
        "  ldo_common.py globals to apply this design:",
        f"    R_FB_TOP = {params['r_fb_top']}",
        f"    R_FB_BOT = {params['r_fb_bot']}",
        f"    R_COMP   = {params['r_comp']:.0f}",
        f"    C_COMP   = {params['c_comp']:.6e}",
        f"    W_M2_UM  = {params['w_m2_um']:.0f}",
        f"    M_M2     = {params['m_m2']}",
        "=" * 60,
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="LDO auto-design: compute R_FB, M2 size, compensation from specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--vout",    type=float, default=1.8,   metavar="V",
                        help="Target VOUT (V) [1.8]")
    parser.add_argument("--vin",     type=float, default=2.3,   metavar="V",
                        help="VIN supply (V) [2.3]")
    parser.add_argument("--iload",   type=float, default=100.0, metavar="mA",
                        help="Max load current (mA) [100]")
    parser.add_argument("--vref",    type=float, default=0.9,   metavar="V",
                        help="Reference voltage (V) [0.9]")
    parser.add_argument("--gbw",     type=float, default=1284.0,metavar="kHz",
                        help="Target GBW (kHz) [1284]")
    parser.add_argument("--fz-frac", type=float, default=0.4,  metavar="F",
                        help="fz/GBW ratio (0.3–0.6) [0.4]")
    parser.add_argument("--no-sim",  action="store_true",
                        help="Skip simulation, show design only")
    args = parser.parse_args()

    # Design
    params = design(
        vout     = args.vout,
        vin      = args.vin,
        iload_ma = args.iload,
        vref     = args.vref,
        gbw_khz  = args.gbw,
        fz_frac  = args.fz_frac,
    )

    # Verify
    sim_metrics = None
    if not args.no_sim:
        sim_metrics = verify(params)

    # Report
    report = _build_report(params, sim_metrics)
    print(f"\n{report}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    rpt_path = LOG_DIR / "ldo_auto_design.txt"
    rpt_path.write_text(report, encoding="utf-8")
    print(f"\n  Report -> {rpt_path.name}")


if __name__ == "__main__":
    main()
