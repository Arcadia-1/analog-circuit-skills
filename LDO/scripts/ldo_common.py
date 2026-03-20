#!/usr/bin/env python3
"""
ldo_common.py
=============
Shared circuit parameters, DUT rendering, and helper functions
for all LDO simulation scripts.
"""

import re as _re
import functools as _functools
import tempfile
import os
from pathlib import Path

import numpy as np

from ngspice_common import (
    LOG_DIR, MODEL_DIR, NETLIST_DUT_DIR, NETLIST_TB_DIR,
    render_template, run_ngspice, spath,
)

# ─────────────────────────────────────────────────────────────────────────────
# Circuit / technology parameters
# ─────────────────────────────────────────────────────────────────────────────
VIN_NOM  = 2.3    # V  nominal input supply  (Spectre: vin=2.3)
VOUT_NOM = 1.8    # V  regulated output (= 2 × VREF)
VREF_NOM = 0.9    # V  bandgap reference     (Spectre: V3 dc=900m)

# Feedback divider: VOUT × R1/(R0+R1) = VREF  →  R0 = R1 for VOUT = 2×VREF
# I_div = 1% × Iload = 1mA → R0+R1 = 1.8k → R0=R1=900Ω  (Spectre: R0/R1=900)
R_FB_TOP = 900    # Ω  R0 (from VOUT to divider midpoint)
R_FB_BOT = 900    # Ω  R1 (from divider midpoint to VSS)

# Compensation zero network
R_COMP = 2000     # Ω  R2  (2 kΩ, unchanged from Spectre: R2=2K)
C_COMP = 160e-12  # F  C0  (160 pF, Spectre: C0 c=160p)
C_IBIAS = 1.0     # F  C1 bypass on ibias node (large, from original schematic)
C_OUT   = 1e-6    # F  C2  (1 uF output cap)

IBIAS_UA = 100    # uA  bias current I1 (vin → ibias)  (Spectre: I1 dc=100u)

# Default load resistor: VOUT/R_LOAD = 1.8/18 = 100 mA  (Spectre: R3=18)
R_LOAD_DEFAULT = 18   # Ω

MODEL_PATH = spath(MODEL_DIR / "ptm180.lib")

# ─────────────────────────────────────────────────────────────────────────────
# Transistor sizes — modify these globals to change device dimensions.
# W_Mxx_UM : width per finger (µm)
# L_Mxx_NM : channel length (nm)
# M_Mxx    : number of parallel fingers (multiplier)
# ─────────────────────────────────────────────────────────────────────────────

# Bias current mirror (NMOS, L=1 µm)
W_M6_UM = 160.0;  L_M6_NM = 1000;  M_M6 = 1     # diode-connected reference (1×)
W_M5_UM = 160.0;  L_M5_NM = 1000;  M_M5 = 10    # 10× tail current mirror

# Differential pair (NMOS, long L for low offset + high gm·ro)
W_M0_UM = 240.0;  L_M0_NM = 2000;  M_M0 = 10    # non-inverting input (VREF)
W_M1_UM = 240.0;  L_M1_NM = 2000;  M_M1 = 10    # inverting input (V_fb)

# PMOS active load (current mirror, L=1 µm)
W_M3_UM =  32.0;  L_M3_NM = 1000;  M_M3 = 10    # mirror output  → net3 (ea out)
W_M4_UM =  32.0;  L_M4_NM = 1000;  M_M4 = 10    # diode-connected → net4

# Pass transistor (large PMOS, sized for ILOAD_max = 100 mA)
W_M2_UM = 120.0;  L_M2_NM =  180;  M_M2 = 100   # 100 mA pass device (Spectre: multi=100)


# ─────────────────────────────────────────────────────────────────────────────
# Model parameter extraction
# Adapted from gmoverid-skill/simulate_gmoverid.py — same BSIM3v3 parser,
# applied to PTM 180nm (NMOS / PMOS, LEVEL=8).
# ─────────────────────────────────────────────────────────────────────────────

@_functools.lru_cache(maxsize=4)
def _parse_lib_params(lib_file, model_name):
    """
    Extract BSIM3v3 parameters from ptm180.lib for the named model.
    Same algorithm as gmoverid-skill/simulate_gmoverid.py::_parse_lib_params().
    Returns dict with lowercase keys; tox/cgso/cgdo in SI (F), nch in cm⁻³.
    """
    params = {}
    in_model = False
    with open(lib_file, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            stripped = line.strip()
            lo = stripped.lower()
            if lo.startswith('.model'):
                tokens = stripped.split()
                if len(tokens) >= 2 and tokens[1].lower() == model_name.lower():
                    in_model = True
                else:
                    in_model = False
                continue
            if not in_model:
                continue
            if stripped and not stripped.startswith('+') and not stripped.startswith('*'):
                in_model = False
                continue
            if not stripped.startswith('+'):
                continue
            content = stripped[1:]
            tokens = _re.split(r'\s+', content.strip())
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok == '=':
                    if i >= 1 and i + 1 < len(tokens):
                        key = tokens[i - 1].lower()
                        try:
                            params[key] = float(tokens[i + 1])
                        except ValueError:
                            pass
                    i += 2
                elif '=' in tok:
                    key, _, val_str = tok.partition('=')
                    key = key.strip().lower()
                    val_str = val_str.strip()
                    if not val_str and i + 1 < len(tokens):
                        val_str = tokens[i + 1]
                        i += 1
                    try:
                        params[key] = float(val_str)
                    except ValueError:
                        pass
                    i += 1
                else:
                    i += 1
    if 'vth0' in params:
        params['vth0'] = abs(params['vth0'])
    return params


def _cox(tox):
    """Gate oxide capacitance per unit area [F/m²]."""
    return 8.854e-12 * 3.9 / tox


def _get_model_params(pol):
    """
    Return PTM 180nm model parameters for NMOS (NMOS) or PMOS (PMOS).

    Returns
    -------
    dict with keys:
      tox   [m],  nch [m⁻³],  cgso [F/m],  cgdo [F/m],  vth0 [V]
    """
    model_name = 'NMOS' if pol == 'nmos' else 'PMOS'
    lib = str(MODEL_DIR / 'ptm180.lib')
    p = _parse_lib_params(lib, model_name)
    if pol == 'nmos':
        return dict(
            tox  = p.get('tox',  4.1e-9),
            nch  = p.get('nch',  2.35e17) * 1e6,   # cm⁻³ → m⁻³
            cgso = p.get('cgso', 7.9e-10),
            cgdo = p.get('cgdo', 7.9e-10),
            vth0 = p.get('vth0', 0.40),
        )
    else:
        return dict(
            tox  = p.get('tox',  4.1e-9),
            nch  = p.get('nch',  6.02e16) * 1e6,   # cm⁻³ → m⁻³
            cgso = p.get('cgso', 6.8e-10),
            cgdo = p.get('cgdo', 6.8e-10),
            vth0 = p.get('vth0', 0.42),
        )


def compute_mos_caps(vgs_v, vds_v, w_um, l_nm, pol='nmos'):
    """
    Analytical gate capacitances (Cgs, Cgd, Cgb, Cgg) for one device finger.
    Uses BSIM3v3 piecewise model — same method as gmoverid-skill.

    Parameters
    ----------
    vgs_v, vds_v : absolute magnitudes [V] (unified NMOS/PMOS convention)
    w_um         : per-finger width [µm]
    l_nm         : channel length [nm]
    pol          : 'nmos' or 'pmos'

    Returns
    -------
    (cgs, cgd, cgb, cgg) [F]
    """
    mp     = _get_model_params(pol)
    tox    = mp['tox']
    nch    = mp['nch']
    cgso   = mp['cgso']
    cgdo   = mp['cgdo']
    vth    = mp['vth0']
    W      = w_um * 1e-6
    L      = l_nm * 1e-9
    cox_i  = _cox(tox) * W * L
    cov_s  = cgso * W
    cov_d  = cgdo * W

    eps_si = 11.7 * 8.854e-12
    phi_f  = 0.02585 * np.log(max(float(nch), 1e15) / 1.45e16)
    W_dep  = np.sqrt(2 * eps_si * max(2 * phi_f, 0.3)
                     / (1.6e-19 * max(float(nch), 1e15)))
    Cdep_a  = eps_si / W_dep
    cgb_dep = _cox(tox) * Cdep_a / (_cox(tox) + Cdep_a) * W * L

    vgs = float(vgs_v)
    vds = float(vds_v)

    def _sig(x, x0, w_):
        return 1.0 / (1.0 + np.exp(np.clip(-(x - x0) / w_, -50, 50)))

    inv_on  = _sig(vgs, vth, 0.05)
    inv_lin = _sig(vgs - vth - vds, 0.0, 0.04)
    cgs_on  = ((2/3)*cox_i + cov_s
               + inv_lin * (0.5*cox_i + cov_s - ((2/3)*cox_i + cov_s)))
    cgd_on  = cov_d + inv_lin * (0.5*cox_i + cov_d - cov_d)
    cgs = float(cov_s + inv_on * (cgs_on - cov_s))
    cgd = float(cov_d + inv_on * (cgd_on - cov_d))
    cgb = float(cgb_dep * (1.0 - inv_on))
    cgg = cgs + cgd + cgb
    return cgs, cgd, cgb, cgg


def mos_derived_metrics(gm_S, gds_S, id_A, vgs_V, vds_V, w_um, l_nm, mult,
                        pol='nmos'):
    """
    Compute gm/ID, gm·ro, fT for a multi-finger transistor at its operating
    point, using the gmoverid methodology (analytical Cgg).

    Parameters
    ----------
    gm_S, gds_S : total gm/gds [S] (sum over all m fingers)
    id_A        : total drain current [A] (signed; |id| used internally)
    vgs_V       : |Vgs| or |Vsg| [V] (absolute value expected)
    vds_V       : |Vds| or |Vsd| [V] (absolute value expected)
    w_um        : per-finger width [µm]
    l_nm        : channel length [nm]
    mult        : number of parallel fingers (m=)
    pol         : 'nmos' or 'pmos'

    Returns
    -------
    dict: gmid, gmro, ft_Hz, vov_V
    """
    id_abs = max(abs(float(id_A)),  1e-13)
    gds_g  = max(float(gds_S),      1e-15)
    gmid   = float(gm_S) / id_abs
    gmro   = float(gm_S) / gds_g

    # fT = gm / (2π × Cgg_total)
    # Cgg per finger computed analytically from model params.
    # Total Cgg = per-finger Cgg × number of fingers.
    _, _, _, cgg_finger = compute_mos_caps(
        abs(float(vgs_V)), abs(float(vds_V)), w_um, l_nm, pol)
    cgg_total = cgg_finger * mult
    ft_Hz     = float(gm_S) / (2.0 * np.pi * max(cgg_total, 1e-20))

    mp    = _get_model_params(pol)
    vov_V = abs(float(vgs_V)) - mp['vth0']
    return dict(gmid=gmid, gmro=gmro, ft_Hz=ft_Hz, vov_V=vov_V)


# ─────────────────────────────────────────────────────────────────────────────
def _mos_params(W_um, L_nm):
    """
    Compute MOSFET area/perimeter parameters for ngspice from W and L.

    PTM 180nm layout rule approximation:
      drain/source extension beyond gate = 270 nm
      perimeter contact end-cap          = 4.32 µm

    Returns (ad, as_, pd, ps, nrd, nrs) as formatted SPICE strings.
    """
    W   = W_um * 1e-6
    EXT = 270e-9       # junction extension (m)
    CAP = 4.32e-6      # contact perimeter addition (m)
    AD  = W * EXT
    AS  = W * EXT
    PD  = W + CAP
    PS  = W + CAP
    NRD = EXT / W
    NRS = EXT / W
    return (f"{AD:.4e}", f"{AS:.4e}", f"{PD:.4e}", f"{PS:.4e}",
            f"{NRD:.7f}", f"{NRS:.7f}")


def _fmt_L(L_nm):
    """Format channel length: 1000 nm → '1u', 180 nm → '180n'."""
    if L_nm >= 1000 and L_nm % 1000 == 0:
        return f"{L_nm // 1000}u"
    return f"{L_nm}n"


# ─────────────────────────────────────────────────────────────────────────────
# DUT rendering
# ─────────────────────────────────────────────────────────────────────────────
def render_dut():
    """
    Render ldo_dut.cir.tmpl → WORK/netlists/dut/ldo_dut.cir.
    Returns (include_line_str, None).

    Reads all circuit globals at call time, so sweep scripts may modify
    module-level variables before calling render_dut() to get new netlists.
    """
    def _mp(W_um, L_nm):
        return _mos_params(W_um, L_nm)

    ad_m6, as_m6, pd_m6, ps_m6, nrd_m6, nrs_m6 = _mp(W_M6_UM, L_M6_NM)
    ad_m5, as_m5, pd_m5, ps_m5, nrd_m5, nrs_m5 = _mp(W_M5_UM, L_M5_NM)
    ad_m0, as_m0, pd_m0, ps_m0, nrd_m0, nrs_m0 = _mp(W_M0_UM, L_M0_NM)
    ad_m1, as_m1, pd_m1, ps_m1, nrd_m1, nrs_m1 = _mp(W_M1_UM, L_M1_NM)
    ad_m3, as_m3, pd_m3, ps_m3, nrd_m3, nrs_m3 = _mp(W_M3_UM, L_M3_NM)
    ad_m4, as_m4, pd_m4, ps_m4, nrd_m4, nrs_m4 = _mp(W_M4_UM, L_M4_NM)
    ad_m2, as_m2, pd_m2, ps_m2, nrd_m2, nrs_m2 = _mp(W_M2_UM, L_M2_NM)

    text = render_template(
        "ldo_dut.cir.tmpl",
        vin_dc   = VIN_NOM,
        vref_dc  = VREF_NOM,
        ibias_ua = IBIAS_UA,
        c_ibias  = f"{C_IBIAS:.6g}",
        r_comp   = R_COMP,
        c_comp   = f"{C_COMP:.6e}",
        r_fb_top = R_FB_TOP,
        r_fb_bot = R_FB_BOT,
        c_out    = f"{C_OUT:.6e}",
        # M6 — bias reference
        w_m6=f"{W_M6_UM}u", l_m6=_fmt_L(L_M6_NM), m_m6=M_M6,
        ad_m6=ad_m6, as_m6=as_m6, pd_m6=pd_m6, ps_m6=ps_m6,
        nrd_m6=nrd_m6, nrs_m6=nrs_m6,
        # M5 — tail mirror
        w_m5=f"{W_M5_UM}u", l_m5=_fmt_L(L_M5_NM), m_m5=M_M5,
        ad_m5=ad_m5, as_m5=as_m5, pd_m5=pd_m5, ps_m5=ps_m5,
        nrd_m5=nrd_m5, nrs_m5=nrs_m5,
        # M0 — diff pair non-inv
        w_m0=f"{W_M0_UM}u", l_m0=_fmt_L(L_M0_NM), m_m0=M_M0,
        ad_m0=ad_m0, as_m0=as_m0, pd_m0=pd_m0, ps_m0=ps_m0,
        nrd_m0=nrd_m0, nrs_m0=nrs_m0,
        # M1 — diff pair inv
        w_m1=f"{W_M1_UM}u", l_m1=_fmt_L(L_M1_NM), m_m1=M_M1,
        ad_m1=ad_m1, as_m1=as_m1, pd_m1=pd_m1, ps_m1=ps_m1,
        nrd_m1=nrd_m1, nrs_m1=nrs_m1,
        # M3 — PMOS active load output
        w_m3=f"{W_M3_UM}u", l_m3=_fmt_L(L_M3_NM), m_m3=M_M3,
        ad_m3=ad_m3, as_m3=as_m3, pd_m3=pd_m3, ps_m3=ps_m3,
        nrd_m3=nrd_m3, nrs_m3=nrs_m3,
        # M4 — PMOS active load diode
        w_m4=f"{W_M4_UM}u", l_m4=_fmt_L(L_M4_NM), m_m4=M_M4,
        ad_m4=ad_m4, as_m4=as_m4, pd_m4=pd_m4, ps_m4=ps_m4,
        nrd_m4=nrd_m4, nrs_m4=nrs_m4,
        # M2 — pass transistor
        w_m2=f"{W_M2_UM}u", l_m2=_fmt_L(L_M2_NM), m_m2=M_M2,
        ad_m2=ad_m2, as_m2=as_m2, pd_m2=pd_m2, ps_m2=ps_m2,
        nrd_m2=nrd_m2, nrs_m2=nrs_m2,
    )
    dut_path = NETLIST_DUT_DIR / "ldo_dut.cir"
    dut_path.write_text(text, encoding="utf-8")
    return f".include {spath(dut_path)}", None


def circuit_params(extra=None):
    """Return parameter dict for plot titles / result logging."""
    p = dict(
        VIN_NOM  = VIN_NOM,
        VOUT_NOM = VOUT_NOM,
        VREF_NOM = VREF_NOM,
        R_FB_TOP = R_FB_TOP,
        R_FB_BOT = R_FB_BOT,
        R_COMP   = R_COMP,
        C_COMP   = C_COMP,
        C_OUT    = C_OUT,
        IBIAS_UA = IBIAS_UA,
    )
    if extra:
        p.update(extra)
    return p


def run_netlist(tmpl_name, kw, log_path, timeout=180):
    """Render template, save to WORK/netlists/testbench/, run ngspice."""
    text = render_template(tmpl_name, **kw)
    save_path = NETLIST_TB_DIR / (Path(log_path).stem + ".cir")
    save_path.write_text(text, encoding="utf-8")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cir", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        tmp = f.name
    try:
        return run_ngspice(tmp, log=log_path, timeout=timeout)
    finally:
        os.unlink(tmp)
