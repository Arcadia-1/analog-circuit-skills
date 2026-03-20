#!/usr/bin/env python3
"""
run_error_amp_design.py
=======================
Design the five-transistor error amplifier for the LDO using the gm/ID
methodology from the gmoverid-skill.

Topology (ldo_dut.cir.tmpl)
---------------------------
  VIN ─── M3(PMOS, mirror) ─── M4(PMOS, diode) ─── VIN
            │(net3, ea out)         │(net4)
    VREF ──M0(NMOS)          V_fb──M1(NMOS)
            │                         │
            └──────── M5(NMOS, tail, 10×) ──── VSS

Five transistors: M0/M1 (diff pair), M3/M4 (PMOS active load), M5 (tail)

Design methodology
------------------
gm/ID is the pivot quantity linking specs to device widths:

  gm/ID chosen  →  Id/W looked up  →  W = Id / Id_W
                →  fT, gm·ro confirmed
                →  Vgs set (bias)

Design steps
------------
  1. ITAIL given (= M5 mirror ratio × IBIAS = 10 × 100 µA = 1 mA)
  2. Id_branch = ITAIL / 2 = 500 µA (each diff-pair branch)
  3. M0/M1 (NMOS): choose gm/ID → id_w → W  (gm sets A_v and GBW)
  4. M3/M4 (PMOS): same Id → choose gm/ID → id_w → W
  5. M5    (NMOS): ITAIL, choose gm/ID → W   (1× reference, m=1)
  6. Report A_v_ea, Ro_ea, estimated LDO GBW, second pole fp2

Usage
-----
  cd LDO/scripts/
  python run_error_amp_design.py
  python run_error_amp_design.py --gmid-inp 15 --gmid-load 8
  python run_error_amp_design.py --sweep         # sweep gm/ID and show trade-offs

Arguments
---------
  --gmid-inp   gm/ID for M0/M1 (default 13)   high → low noise, high gm·ro
  --gmid-load  gm/ID for M3/M4 (default 10)   high → low power, lower gm
  --sweep      show A_v and fp2 vs gm/ID table instead of single design point

Model
-----
  Uses ptm180.lib (NMOS / PMOS, BSIM3v3 Level 8) — same model as the
  LDO simulations. GmIdTable adds it to MODEL_INFO at runtime; no skill files
  are modified.

Output
------
  Console report of transistor sizes and performance metrics.
"""

import sys
import os
import argparse
import math
from pathlib import Path

import numpy as np

# ── Locate gmoverid-skill and import its API ──────────────────────────────────
_THIS = Path(__file__).resolve()
_GMOVERID_ASSETS = _THIS.parents[2] / 'gmoverid-skill' / 'gmoverid' / 'assets'
if not _GMOVERID_ASSETS.exists():
    sys.exit(
        f"ERROR: gmoverid-skill not found at {_GMOVERID_ASSETS}\n"
        "Expected repo layout: analog-circuit-skills/gmoverid-skill/gmoverid/assets/"
    )
sys.path.insert(0, str(_GMOVERID_ASSETS))
sys.path.insert(0, str(_THIS.parent))

import simulate_gmoverid as _sim_mod
from simulate_gmoverid import MODEL_INFO
from design_gmoverid import GmIdTable, print_op
import ldo_common as ldo

# Patch _ngspice() so gmoverid-skill finds ngspice on Windows the same way
# ldo_common's find_ngspice() does (checks hardcoded installation paths).
def _patched_ngspice():
    import shutil, sys
    from pathlib import Path as _P
    for exe in ('ngspice_con', 'ngspice'):
        if shutil.which(exe):
            return exe
    candidates = [
        r"C:\Program Files\ngspice-45.2_64\Spice64\bin\ngspice_con.exe",
        r"C:\Program Files\ngspice-45.2_64\Spice64\bin\ngspice.exe",
        r"C:\Program Files\Spice64\bin\ngspice_con.exe",
        r"C:\Program Files\Spice64\bin\ngspice.exe",
    ]
    for c in candidates:
        if _P(c).exists():
            return c
    raise RuntimeError('ngspice not found in PATH or standard installation paths')

_sim_mod._ngspice = _patched_ngspice

# ── Register PTM 180nm models at runtime (no skill file modified) ─────────────
_PTM_LIB = _THIS.parents[1] / 'assets' / 'models' / 'ptm180.lib'
if not _PTM_LIB.exists():
    sys.exit(f"ERROR: ptm180.lib not found at {_PTM_LIB}")

MODEL_INFO['NMOS'] = dict(
    pol='nmos', file=_PTM_LIB, model_name='NMOS',
    vdd=1.8, vgs_stop=1.8, vds_stop=1.8,
)
MODEL_INFO['PMOS'] = dict(
    pol='pmos', file=_PTM_LIB, model_name='PMOS',
    vdd=1.8, vgs_stop=1.8, vds_stop=1.8,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Circuit constants
# ═══════════════════════════════════════════════════════════════════════════════

VDD       = ldo.VIN_NOM                          # 2.3 V  (LDO input)
IBIAS_A   = ldo.IBIAS_UA * 1e-6                  # 100 µA  (1× reference)
ITAIL     = IBIAS_A * ldo.M_M5                   # 1 mA   (10× tail)
ID_BRANCH = ITAIL / 2.0                          # 500 µA  per diff-pair branch

# Channel lengths matching original schematic
L_INP_UM  = ldo.L_M0_NM * 1e-3    # 2 µm  — long for low offset + high gm·ro
L_LOAD_UM = ldo.L_M3_NM * 1e-3    # 1 µm  — PMOS active load
L_TAIL_UM = ldo.L_M5_NM * 1e-3    # 1 µm  — tail NMOS

# Finger widths kept at original values (W_per_finger); multiplier m is designed
W_FINGER_INP  = float(ldo.W_M0_UM)   # 240 µm per finger
W_FINGER_LOAD = float(ldo.W_M3_UM)   #  32 µm per finger
W_FINGER_TAIL = float(ldo.W_M5_UM)   # 160 µm per finger  (1× reference, m=1)

# Vds operating points for characterisation
#   M0 drain (net3) ≈ VIN − |VGS_M3| ≈ 2.3 − 0.55 ≈ 1.75 V
#   M0 source (tail) ≈ 0.15 V  →  VDS_M0 ≈ 1.6 V  →  use 0.9 V (VDD/2) as typical
VDS_INP  = 0.9   # V  |Vds| for NMOS diff pair  (conservative, in saturation)
VDS_LOAD = 0.7   # V  |Vsd| for PMOS active load (net3 ≈ 0.5–0.7 V from VIN)


# ═══════════════════════════════════════════════════════════════════════════════
#  Build lookup tables (run once, cached to gmoverid-skill/gmoverid/assets/logs/cache/)
# ═══════════════════════════════════════════════════════════════════════════════

_tbl_n = None   # GmIdTable for NMOS
_tbl_p = None   # GmIdTable for PMOS


def _get_tables():
    global _tbl_n, _tbl_p
    if _tbl_n is None:
        print("\n  Building gm/ID tables for PTM 180nm ...")
        print(f"  NMOS  W=1um  L={L_INP_UM*1e3:.0f}nm  Vds={VDS_INP}V")
        _tbl_n = GmIdTable('NMOS', W=1.0, L=L_INP_UM, vds=VDS_INP)
        print(f"  PMOS  W=1um  L={L_LOAD_UM*1e3:.0f}nm  |Vsd|={VDS_LOAD}V")
        _tbl_p = GmIdTable('PMOS', W=1.0, L=L_LOAD_UM, vds=VDS_LOAD)
    return _tbl_n, _tbl_p


# ═══════════════════════════════════════════════════════════════════════════════
#  Core design function
# ═══════════════════════════════════════════════════════════════════════════════

def design_5t_ota(gmid_inp=13.0, gmid_load=10.0, verbose=True):
    """
    Size the five-transistor error amplifier at given gm/ID operating points.

    Parameters
    ----------
    gmid_inp  : gm/ID for M0/M1 input NMOS [V⁻¹]
    gmid_load : gm/ID for M3/M4 load PMOS  [V⁻¹]
    verbose   : print detailed report

    Returns
    -------
    dict with all designed parameters and performance metrics
    """
    tbl_n, tbl_p = _get_tables()
    sep = "=" * 60

    if verbose:
        print(f"\n{sep}")
        print(f"  Five-Transistor OTA — gm/ID Design")
        print(f"  ITAIL = {ITAIL*1e3:.1f} mA  "
              f"Id/branch = {ID_BRANCH*1e6:.0f} uA")
        print(f"  gmid_inp={gmid_inp:.1f} V^-1   "
              f"gmid_load={gmid_load:.1f} V^-1")
        print(sep)

    # ── [1] Input diff pair M0/M1 (NMOS) ──────────────────────────────────
    op_inp = tbl_n.size(gmid=gmid_inp, Id=ID_BRANCH)
    W_inp_total = op_inp['W_um']
    m_inp = max(1, round(W_inp_total / W_FINGER_INP))
    W_inp_actual = W_FINGER_INP * m_inp
    Id_inp_actual = W_inp_actual * op_inp['id_w_Apm'] * 1e-6

    if verbose:
        print(f"\n  [1] M0/M1  NMOS  L={L_INP_UM*1e3:.0f}nm")
        print_op(op_inp)
        print(f"       W_total = {W_inp_total:.1f} um  "
              f"→  W={W_FINGER_INP:.0f}um × m={m_inp}"
              f"  (W_actual={W_inp_actual:.0f}um)")

    # ── [2] PMOS active load M3/M4 (PMOS) ─────────────────────────────────
    op_load = tbl_p.size(gmid=gmid_load, Id=ID_BRANCH)
    W_load_total = op_load['W_um']
    m_load = max(1, round(W_load_total / W_FINGER_LOAD))
    W_load_actual = W_FINGER_LOAD * m_load
    Id_load_actual = W_load_actual * op_load['id_w_Apm'] * 1e-6

    if verbose:
        print(f"\n  [2] M3/M4  PMOS  L={L_LOAD_UM*1e3:.0f}nm")
        print_op(op_load)
        print(f"       W_total = {W_load_total:.1f} um  "
              f"→  W={W_FINGER_LOAD:.0f}um × m={m_load}"
              f"  (W_actual={W_load_actual:.0f}um)")

    # ── [3] Performance metrics ───────────────────────────────────────────────
    gm_ea   = op_inp['gm_S']                        # total gm (at Id_branch)
    gmro_n  = op_inp['gmro']
    gmro_p  = op_load['gmro']
    ro_n    = gmro_n / gm_ea                        # ro of M0 (one finger sized)
    ro_p    = gmro_p / op_load['gm_S']              # ro of M3
    Ro_ea   = (ro_n * ro_p) / (ro_n + ro_p)        # Ro_ea = ro_M0 || ro_M3
    A_v_ea  = gm_ea * Ro_ea                         # DC gain of error amp

    # Pass-gate Cgg: loads net3 and creates the second pole of the LDO loop
    _, _, _, cgg_finger = ldo.compute_mos_caps(
        vgs_v=0.8, vds_v=0.5,
        w_um=ldo.W_M2_UM, l_nm=ldo.L_M2_NM, pol='pmos')
    Cgs_M2_total = cgg_finger * ldo.M_M2

    fp2_ea = 1.0 / (2.0 * math.pi * Ro_ea * Cgs_M2_total)

    # Estimated LDO loop GBW (first-order):
    #   GBW = gm_ea × Ro_ea × gm_M2 × beta / (2π × C_OUT)
    # gm_M2 ≈ 2 × Id_M2 / Vov_M2;  at 100 mA, Vov ≈ 0.3 V → gm_M2 ≈ 0.67 A/V
    gm_M2_est = 2.0 * 0.1 / 0.3
    beta      = ldo.R_FB_BOT / (ldo.R_FB_TOP + ldo.R_FB_BOT)
    GBW_est   = (gm_ea * Ro_ea * gm_M2_est * beta) / (2.0 * math.pi * ldo.C_OUT)

    # fT of diff pair (from table, for reference)
    fT_inp_GHz = op_inp['ft_Hz'] / 1e9

    if verbose:
        print(f"\n  {'─'*56}")
        print(f"  Error Amplifier Performance")
        print(f"  {'─'*56}")
        print(f"  gm_ea     = {gm_ea*1e3:.2f} mA/V")
        print(f"  gm·ro_n   = {gmro_n:.1f}   "
              f"ro_M0 = {ro_n/1e3:.1f} kOhm")
        print(f"  gm·ro_p   = {gmro_p:.1f}   "
              f"ro_M3 = {ro_p/1e3:.1f} kOhm")
        print(f"  Ro_ea     = {Ro_ea/1e3:.2f} kOhm  "
              f"(ro_M0 || ro_M3)")
        print(f"  A_v_ea    = {A_v_ea:.1f}  "
              f"({20*math.log10(A_v_ea):.1f} dB)")
        print(f"  fT (inp)  = {fT_inp_GHz:.1f} GHz")
        print(f"")
        print(f"  Cgs_M2    = {Cgs_M2_total*1e12:.1f} pF  (pass gate, loads net3)")
        print(f"  fp2_ea    = {fp2_ea/1e3:.0f} kHz  (2nd pole: 1/(2pi·Ro_ea·Cgs_M2))")
        print(f"  GBW_ldo   ≈ {GBW_est/1e3:.0f} kHz  "
              f"(est: gm_ea·Ro_ea·gm_M2·beta / 2pi·C_OUT)")
        print(f"")
        print(f"  {'─'*56}")
        print(f"  Transistor Sizes")
        print(f"  {'─'*56}")
        vgs_n  = op_inp['Vgs_V']
        vgs_p  = op_load['Vgs_V']
        print(f"  M0/M1  NMOS  "
              f"W={W_FINGER_INP:.0f}um x m={m_inp}  "
              f"L={L_INP_UM*1e3:.0f}nm  "
              f"Vgs={vgs_n:.3f}V")
        print(f"  M3/M4  PMOS  "
              f"W={W_FINGER_LOAD:.0f}um x m={m_load}  "
              f"L={L_LOAD_UM*1e3:.0f}nm  "
              f"|Vsg|={vgs_p:.3f}V")
        print(f"  M5     NMOS  "
              f"W={W_FINGER_TAIL:.0f}um x m=1   "
              f"L={L_TAIL_UM*1e3:.0f}nm  "
              f"(1x ref, m=10 mirror)")
        print(f"")
        print(f"  Original (schematic): "
              f"M0/M1 m={ldo.M_M0}  M3/M4 m={ldo.M_M3}")
        print(sep)

        # PM sanity hint
        if fp2_ea < GBW_est * 3:
            print(f"  WARN: fp2_ea ({fp2_ea/1e3:.0f} kHz) < 3 × GBW_ldo "
                  f"({GBW_est/1e3:.0f} kHz).")
            print(f"  The second pole degrades PM. Consider:")
            print(f"    → Reduce L_inp (lower Ro_ea, raise fp2) or")
            print(f"    → Reduce R_COMP × C_COMP (lower GBW_ldo)")
        else:
            print(f"  OK: fp2_ea / GBW_ldo = "
                  f"{fp2_ea/GBW_est:.1f}x  (>3x: adequate PM margin)")

    return dict(
        gmid_inp=gmid_inp, gmid_load=gmid_load,
        gm_ea=gm_ea, Ro_ea=Ro_ea, A_v_ea=A_v_ea,
        ro_n=ro_n, ro_p=ro_p,
        fp2_ea=fp2_ea, GBW_est=GBW_est,
        Cgs_M2_total=Cgs_M2_total,
        m_inp=m_inp, m_load=m_load,
        W_inp=W_FINGER_INP, W_load=W_FINGER_LOAD,
        fT_inp_Hz=op_inp['ft_Hz'],
        Vgs_inp=op_inp['Vgs_V'], Vgs_load=op_load['Vgs_V'],
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Sweep mode: show trade-offs across gm/ID range
# ═══════════════════════════════════════════════════════════════════════════════

def sweep_gmid():
    """Print a table of A_v_ea, fp2, GBW vs different gmid_inp values."""
    tbl_n, tbl_p = _get_tables()
    gmid_load_fixed = 10.0
    gmid_range = [6, 8, 10, 12, 13, 15, 18, 20]

    print(f"\n  gm/ID Sweep — M0/M1  (gmid_load={gmid_load_fixed} fixed)")
    print(f"  {'gmid_inp':>10} {'gm_ea(mA/V)':>12} {'A_v_ea(dB)':>11} "
          f"{'Ro_ea(kO)':>10} {'fp2(kHz)':>9} {'GBW_est(kHz)':>13} "
          f"{'m_M0':>6} {'fT(GHz)':>8}")
    print(f"  {'─'*90}")

    for gmid_inp in gmid_range:
        r = design_5t_ota(gmid_inp=gmid_inp,
                          gmid_load=gmid_load_fixed, verbose=False)
        ratio = r['fp2_ea'] / r['GBW_est']
        flag = "  <<WARN PM" if ratio < 3 else ""
        print(f"  {gmid_inp:>10.1f} "
              f"{r['gm_ea']*1e3:>12.2f} "
              f"{20*math.log10(r['A_v_ea']):>11.1f} "
              f"{r['Ro_ea']/1e3:>10.2f} "
              f"{r['fp2_ea']/1e3:>9.0f} "
              f"{r['GBW_est']/1e3:>13.0f} "
              f"{r['m_inp']:>6} "
              f"{r['fT_inp_Hz']/1e9:>8.1f}"
              f"{flag}")

    print(f"\n  Interpretation:")
    print(f"    gmid_inp high (>15) → more gm·ro, higher A_v_ea, but m_M0 grows fast")
    print(f"    gmid_inp low  (<10) → less gm·ro, lower gain, but fT higher")
    print(f"    fp2_ea must be >> GBW_ldo (~1300 kHz) to preserve phase margin")
    print(f"    Recommended: gmid_inp = 12-15 (balanced gain + fp2 margin)")


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="gm/ID sizing of 5T error amplifier for PTM 180nm LDO")
    parser.add_argument('--gmid-inp',  type=float, default=13.0,
                        help="gm/ID for M0/M1 input NMOS [V^-1] (default: 13)")
    parser.add_argument('--gmid-load', type=float, default=10.0,
                        help="gm/ID for M3/M4 PMOS load [V^-1] (default: 10)")
    parser.add_argument('--sweep', action='store_true',
                        help="print trade-off table across gm/ID range")
    args = parser.parse_args()

    if args.sweep:
        sweep_gmid()
    else:
        design_5t_ota(gmid_inp=args.gmid_inp, gmid_load=args.gmid_load)


if __name__ == '__main__':
    main()
