#!/usr/bin/env python3
"""
simulate_ldo_op.py
==================
DC operating-point analysis -- per-transistor gm/ID, gm*ro, fT.

Uses a flat testbench (all devices at top level, no subcircuit) so that
ngspice can access device parameters via @m0[gm] etc. directly.

Each of the 5 parameters (gm, gds, id, vgs, vds) is written to a separate
wrdata file; Python reads data[0, 1] to get the scalar value.

Derived metrics use the gmoverid methodology:
  gm/ID  -- from simulated gm and |id|
  gm*ro  -- from simulated gm and gds
  fT     -- gm / (2*pi*Cgg_total); Cgg from analytical BSIM3v3 piecewise model
             with parameters extracted from ptm180.lib (same as gmoverid-skill)
  Vov    -- |Vgs| - VTH0 (VTH0 from model file)

Public API
----------
simulate_op() -> dict
    'transistors' : list of 7 per-device dicts
    'params'      : circuit / simulation parameters
    'rc'          : ngspice return code

Per-device dict keys:
    name, role, pol, w_um, l_nm, mult,
    gm [S], gds [S], id [A], vgs [V], vds [V],
    gmid [V^-1], gmro, ft_Hz [Hz], vov_V [V]
"""

import time

from ngspice_common import LOG_DIR, parse_wrdata, spath
import ldo_common as _ldo
from ldo_common import (
    VIN_NOM, VREF_NOM, MODEL_PATH, R_LOAD_DEFAULT,
    C_IBIAS, R_COMP, C_COMP, C_OUT, R_FB_TOP, R_FB_BOT, IBIAS_UA,
    circuit_params, run_netlist,
    mos_derived_metrics,
    _mos_params, _fmt_L,
)

_PARAMS = ('gm', 'gds', 'id', 'vgs', 'vds')


def simulate_op() -> dict:
    """Run DC .op analysis and extract per-transistor operating points."""
    print("\n=== LDO Operating-Point Analysis ===")
    return _run_op()


# -----------------------------------------------------------------------------
def _run_op():
    tag = "ldo_op"
    print(f"  [{tag}] starting ...", flush=True)
    t0 = time.perf_counter()

    # Device definitions read at call time (sweep scripts may change globals).
    devices = [
        ('m6', 'Bias ref (diode-conn)', 'nmos',
         _ldo.W_M6_UM, _ldo.L_M6_NM, _ldo.M_M6),
        ('m5', 'Tail mirror 10x',       'nmos',
         _ldo.W_M5_UM, _ldo.L_M5_NM, _ldo.M_M5),
        ('m0', 'Diff pair non-inv',     'nmos',
         _ldo.W_M0_UM, _ldo.L_M0_NM, _ldo.M_M0),
        ('m1', 'Diff pair inv',         'nmos',
         _ldo.W_M1_UM, _ldo.L_M1_NM, _ldo.M_M1),
        ('m4', 'Load diode (PMOS)',     'pmos',
         _ldo.W_M4_UM, _ldo.L_M4_NM, _ldo.M_M4),
        ('m3', 'Load output (PMOS)',    'pmos',
         _ldo.W_M3_UM, _ldo.L_M3_NM, _ldo.M_M3),
        ('m2', 'Pass transistor',       'pmos',
         _ldo.W_M2_UM, _ldo.L_M2_NM, _ldo.M_M2),
    ]

    log = LOG_DIR / f"{tag}.log"

    # One file per (transistor, parameter) = 7 * 5 = 35 files
    paths = {
        f"{name}_{par}": LOG_DIR / f"{tag}_{name}_{par}.txt"
        for name, *_ in devices
        for par in _PARAMS
    }

    kw = _build_kw(devices, paths)
    rc = run_netlist("testbench_ldo_op.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{tag}] exit {rc}, {elapsed:.1f}s", flush=True)

    transistors = []
    for name, role, pol, w_um, l_nm, mult in devices:
        vals = {}
        ok   = True
        for par in _PARAMS:
            p    = paths[f"{name}_{par}"]
            data = parse_wrdata(p) if p.exists() else None
            if data is None or len(data) == 0:
                ok = False
                break
            vals[par] = float(data[0, 1])

        if not ok:
            print(f"  [op] {name}: data missing -- skip", flush=True)
            transistors.append(dict(
                name=name, role=role, pol=pol,
                w_um=w_um, l_nm=l_nm, mult=mult,
                gm=None, gds=None, id=None, vgs=None, vds=None,
            ))
            continue

        m = mos_derived_metrics(
            vals['gm'], vals['gds'], vals['id'],
            vals['vgs'], vals['vds'],
            w_um, l_nm, mult, pol,
        )
        transistors.append(dict(
            name=name, role=role, pol=pol,
            w_um=w_um, l_nm=l_nm, mult=mult,
            gm=vals['gm'], gds=vals['gds'], id=vals['id'],
            vgs=vals['vgs'], vds=vals['vds'],
            **m,
        ))

    _print_op_table(transistors)

    return dict(
        transistors = transistors,
        rc          = rc,
        params      = circuit_params({"VIN_NOM": VIN_NOM}),
    )


def _build_kw(devices, paths):
    """Build flat-netlist template kwargs from current ldo_common globals."""
    def _mp(W, L):
        return _mos_params(W, L)

    ad_m6, as_m6, pd_m6, ps_m6, nrd_m6, nrs_m6 = _mp(_ldo.W_M6_UM, _ldo.L_M6_NM)
    ad_m5, as_m5, pd_m5, ps_m5, nrd_m5, nrs_m5 = _mp(_ldo.W_M5_UM, _ldo.L_M5_NM)
    ad_m0, as_m0, pd_m0, ps_m0, nrd_m0, nrs_m0 = _mp(_ldo.W_M0_UM, _ldo.L_M0_NM)
    ad_m1, as_m1, pd_m1, ps_m1, nrd_m1, nrs_m1 = _mp(_ldo.W_M1_UM, _ldo.L_M1_NM)
    ad_m4, as_m4, pd_m4, ps_m4, nrd_m4, nrs_m4 = _mp(_ldo.W_M4_UM, _ldo.L_M4_NM)
    ad_m3, as_m3, pd_m3, ps_m3, nrd_m3, nrs_m3 = _mp(_ldo.W_M3_UM, _ldo.L_M3_NM)
    ad_m2, as_m2, pd_m2, ps_m2, nrd_m2, nrs_m2 = _mp(_ldo.W_M2_UM, _ldo.L_M2_NM)

    kw = dict(
        vin_dc     = VIN_NOM,
        vref_dc    = VREF_NOM,
        r_load     = R_LOAD_DEFAULT,
        ibias_ua   = IBIAS_UA,
        c_ibias    = f"{C_IBIAS:.6g}",
        r_comp     = R_COMP,
        c_comp     = f"{C_COMP:.6e}",
        r_fb_top   = R_FB_TOP,
        r_fb_bot   = R_FB_BOT,
        c_out      = f"{C_OUT:.6e}",
        model_path = MODEL_PATH,
        # M6
        w_m6=f"{_ldo.W_M6_UM}u", l_m6=_fmt_L(_ldo.L_M6_NM), m_m6=_ldo.M_M6,
        ad_m6=ad_m6, as_m6=as_m6, pd_m6=pd_m6, ps_m6=ps_m6,
        nrd_m6=nrd_m6, nrs_m6=nrs_m6,
        # M5
        w_m5=f"{_ldo.W_M5_UM}u", l_m5=_fmt_L(_ldo.L_M5_NM), m_m5=_ldo.M_M5,
        ad_m5=ad_m5, as_m5=as_m5, pd_m5=pd_m5, ps_m5=ps_m5,
        nrd_m5=nrd_m5, nrs_m5=nrs_m5,
        # M0
        w_m0=f"{_ldo.W_M0_UM}u", l_m0=_fmt_L(_ldo.L_M0_NM), m_m0=_ldo.M_M0,
        ad_m0=ad_m0, as_m0=as_m0, pd_m0=pd_m0, ps_m0=ps_m0,
        nrd_m0=nrd_m0, nrs_m0=nrs_m0,
        # M1
        w_m1=f"{_ldo.W_M1_UM}u", l_m1=_fmt_L(_ldo.L_M1_NM), m_m1=_ldo.M_M1,
        ad_m1=ad_m1, as_m1=as_m1, pd_m1=pd_m1, ps_m1=ps_m1,
        nrd_m1=nrd_m1, nrs_m1=nrs_m1,
        # M4
        w_m4=f"{_ldo.W_M4_UM}u", l_m4=_fmt_L(_ldo.L_M4_NM), m_m4=_ldo.M_M4,
        ad_m4=ad_m4, as_m4=as_m4, pd_m4=pd_m4, ps_m4=ps_m4,
        nrd_m4=nrd_m4, nrs_m4=nrs_m4,
        # M3
        w_m3=f"{_ldo.W_M3_UM}u", l_m3=_fmt_L(_ldo.L_M3_NM), m_m3=_ldo.M_M3,
        ad_m3=ad_m3, as_m3=as_m3, pd_m3=pd_m3, ps_m3=ps_m3,
        nrd_m3=nrd_m3, nrs_m3=nrs_m3,
        # M2
        w_m2=f"{_ldo.W_M2_UM}u", l_m2=_fmt_L(_ldo.L_M2_NM), m_m2=_ldo.M_M2,
        ad_m2=ad_m2, as_m2=as_m2, pd_m2=pd_m2, ps_m2=ps_m2,
        nrd_m2=nrd_m2, nrs_m2=nrs_m2,
        # Output files (one per transistor per parameter)
        **{f"out_{k}": spath(v) for k, v in paths.items()},
    )
    return kw


# -----------------------------------------------------------------------------
def _print_op_table(transistors):
    """Print formatted per-transistor operating-point table."""
    nan = float('nan')
    print()
    print("=" * 84)
    print(f"  Transistor Op-Points  VIN={VIN_NOM}V, VOUT~1.8V, ILOAD=100mA nom.")
    print("  gm/ID, gm*ro, fT: gmoverid methodology (PTM 180nm model + analytical Cgg)")
    print("-" * 84)
    hdr = (f"  {'Dev':<4}  {'Role':<24}  {'Id(uA)':<9}  "
           f"{'|Vgs|(V)':<9}  {'Vov(V)':<7}  "
           f"{'gm/ID':<7}  {'gm*ro':<7}  {'fT(MHz)'}")
    print(hdr)
    print("-" * 84)
    for t in transistors:
        if t.get('gm') is None:
            print(f"  {t['name'].upper():<4}  {t['role']:<24}  -- no data --")
            continue
        id_ua   = abs(t['id'])           * 1e6
        vgs_v   = abs(t['vgs'])
        vov_v   = t.get('vov_V',  nan)
        gmid    = t.get('gmid',   nan)
        gmro    = t.get('gmro',   nan)
        ft_mhz  = t.get('ft_Hz',  nan) / 1e6
        print(f"  {t['name'].upper():<4}  {t['role']:<24}  {id_ua:<9.1f}  "
              f"{vgs_v:<9.3f}  {vov_v:<7.3f}  "
              f"{gmid:<7.1f}  {gmro:<7.1f}  {ft_mhz:.1f}")
    print("=" * 84)
