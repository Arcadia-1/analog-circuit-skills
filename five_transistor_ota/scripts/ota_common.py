#!/usr/bin/env python3
"""Circuit parameters and rendering helpers for the five-transistor OTA."""

from pathlib import Path

from ngspice_common import (
    LOG_DIR, MODEL_DIR, NETLIST_DUT_DIR,
    render_template, run_rendered_netlist, spath,
)

VDD = 1.8
VCM = 0.9
VBIAS = 0.72

R_LOAD = 1e9
C_LOAD = 1e-12

W_IN_UM = 20.0
L_IN_NM = 1000
M_IN = 1

W_LOAD_UM = 16.0
L_LOAD_NM = 1000
M_LOAD = 1

W_TAIL_UM = 12.0
L_TAIL_NM = 1000
M_TAIL = 1

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


def render_dut():
    ad_in, as_in, pd_in, ps_in, nrd_in, nrs_in = _mos_params(W_IN_UM)
    ad_load, as_load, pd_load, ps_load, nrd_load, nrs_load = _mos_params(W_LOAD_UM)
    ad_tail, as_tail, pd_tail, ps_tail, nrd_tail, nrs_tail = _mos_params(W_TAIL_UM)

    text = render_template(
        "five_transistor_ota.cir.tmpl",
        l_in=_fmt_l(L_IN_NM),
        w_in=f"{W_IN_UM}u",
        m_in=M_IN,
        ad_in=ad_in, as_in=as_in, pd_in=pd_in, ps_in=ps_in, nrd_in=nrd_in, nrs_in=nrs_in,
        l_load=_fmt_l(L_LOAD_NM),
        w_load=f"{W_LOAD_UM}u",
        m_load=M_LOAD,
        ad_load=ad_load, as_load=as_load, pd_load=pd_load, ps_load=ps_load,
        nrd_load=nrd_load, nrs_load=nrs_load,
        l_tail=_fmt_l(L_TAIL_NM),
        w_tail=f"{W_TAIL_UM}u",
        m_tail=M_TAIL,
        ad_tail=ad_tail, as_tail=as_tail, pd_tail=pd_tail, ps_tail=ps_tail,
        nrd_tail=nrd_tail, nrs_tail=nrs_tail,
    )
    path = NETLIST_DUT_DIR / "five_transistor_ota_dut.cir"
    path.write_text(text, encoding="utf-8")
    return f".include {spath(path)}"


def common_kw(dut_include):
    return dict(
        vdd=VDD,
        vcm=VCM,
        vbias=VBIAS,
        r_load=f"{R_LOAD:.6g}",
        c_load=f"{C_LOAD:.6e}",
        dut_include=dut_include,
        model_path=MODEL_PATH,
    )


def run_netlist(tmpl_name, kw, log_name, timeout=180):
    return run_rendered_netlist(tmpl_name, kw, LOG_DIR / log_name, timeout=timeout)


def params(extra=None):
    p = dict(
        VDD=VDD, VCM=VCM, VBIAS=VBIAS,
        R_LOAD=R_LOAD, C_LOAD=C_LOAD,
        W_IN_UM=W_IN_UM, L_IN_NM=L_IN_NM, M_IN=M_IN,
        W_LOAD_UM=W_LOAD_UM, L_LOAD_NM=L_LOAD_NM, M_LOAD=M_LOAD,
        W_TAIL_UM=W_TAIL_UM, L_TAIL_NM=L_TAIL_NM, M_TAIL=M_TAIL,
    )
    if extra:
        p.update(extra)
    return p
