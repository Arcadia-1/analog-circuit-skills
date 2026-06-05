#!/usr/bin/env python3
"""Circuit parameters and rendering helpers for the two-stage op amp."""

from ngspice_common import (
    LOG_DIR, MODEL_DIR, NETLIST_DUT_DIR,
    render_template, run_rendered_netlist, spath,
)

VDD = 1.8
VCM = 0.9
IBIAS = 120e-6

CC = 12.0e-12
CL = 1.2e-12
R_LEAK = 1e9

L_ALL_NM = 500

W_M0_M1_UM = 160.0
M_M0_M1 = 1

W_M3_M4_UM = 60.0
M_M3_M4 = 1

W_M2_UM = 720.0
M_M2 = 1

W_M5_M7_UM = 120.0
M_M5_M7 = 1

W_M6_UM = 680.0
M_M6 = 1

MODEL_PATH = spath(MODEL_DIR / "ptm180.lib")


def _fmt_l(l_nm):
    if l_nm >= 1000 and l_nm % 1000 == 0:
        return f"{l_nm // 1000}u"
    return f"{l_nm}n"


def _mos_params(w_um):
    w = w_um * 1e-6
    ext = 270e-9
    cap = 4.32e-6
    ad = w * ext
    pd = w + cap
    nrd = ext / w
    return (
        f"{ad:.4e}", f"{ad:.4e}",
        f"{pd:.4e}", f"{pd:.4e}",
        f"{nrd:.7f}", f"{nrd:.7f}",
    )


def _dev(prefix, w_um, m):
    ad, ass, pd, ps, nrd, nrs = _mos_params(w_um)
    return {
        f"l_{prefix}": _fmt_l(L_ALL_NM),
        f"w_{prefix}": f"{w_um}u",
        f"m_{prefix}": m,
        f"ad_{prefix}": ad,
        f"as_{prefix}": ass,
        f"pd_{prefix}": pd,
        f"ps_{prefix}": ps,
        f"nrd_{prefix}": nrd,
        f"nrs_{prefix}": nrs,
    }


def render_dut():
    kw = {}
    kw.update(_dev("m0_m1", W_M0_M1_UM, M_M0_M1))
    kw.update(_dev("m3_m4", W_M3_M4_UM, M_M3_M4))
    kw.update(_dev("m2", W_M2_UM, M_M2))
    kw.update(_dev("m5_m7", W_M5_M7_UM, M_M5_M7))
    kw.update(_dev("m6", W_M6_UM, M_M6))
    text = render_template(
        "two_stage_opamp.cir.tmpl",
        ibias=f"{IBIAS:.6e}",
        cc=f"{CC:.6e}",
        **kw,
    )
    path = NETLIST_DUT_DIR / "two_stage_opamp_dut.cir"
    path.write_text(text, encoding="utf-8")
    return f".include {spath(path)}"


def common_kw(dut_include):
    return dict(
        vdd=VDD,
        vcm=VCM,
        cl=f"{CL:.6e}",
        r_leak=f"{R_LEAK:.6g}",
        dut_include=dut_include,
        model_path=MODEL_PATH,
    )


def run_netlist(tmpl_name, kw, log_name, timeout=180):
    return run_rendered_netlist(tmpl_name, kw, LOG_DIR / log_name, timeout=timeout)


def params(extra=None):
    p = dict(
        VDD=VDD, VCM=VCM, IBIAS=IBIAS, CC=CC, CL=CL, R_LEAK=R_LEAK,
        L_ALL_NM=L_ALL_NM,
        W_M0_M1_UM=W_M0_M1_UM, M_M0_M1=M_M0_M1,
        W_M3_M4_UM=W_M3_M4_UM, M_M3_M4=M_M3_M4,
        W_M2_UM=W_M2_UM, M_M2=M_M2,
        W_M5_M7_UM=W_M5_M7_UM, M_M5_M7=M_M5_M7,
        W_M6_UM=W_M6_UM, M_M6=M_M6,
    )
    if extra:
        p.update(extra)
    return p
