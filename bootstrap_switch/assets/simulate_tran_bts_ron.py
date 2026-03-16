#!/usr/bin/env python3
"""
simulate_tran_bts_ron.py
========================
Ron comparison: NMOS, PMOS, CMOS, and bootstrap switch.

Uses transistor gds (drain-source conductance) saved during transient analysis.
Ron = 1 / gds  — measured mid-sampling, averaged across all CLK cycles.

Supports multi-node runs via NODE_CONFIGS.
"""

import os
import time
import numpy as np

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bootstrap_common import (
    LOG_DIR, VDD as VDD_DEFAULT, FCLK as FCLK_DEFAULT, TCLK as TCLK_DEFAULT,
    CS as CS_DEFAULT, W, L_NM as L_NM_DEFAULT,
    render_dut, common_kw, run_netlist, parse_wrdata, spath,
    MODEL_DIR, circuit_params,
)

RON_NCYC  = 60
RON_TSTEP = 200e-12   # 200 ps — coarser step is fine for gds measurement

NODE_CONFIGS = [
    {"name": "180nm", "VDD": 1.8, "model": "ptm180.lib",  "L_nm": 180, "W_sw": 10.0},
    {"name": "45nm",  "VDD": 1.0, "model": "ptm45hp.lib", "L_nm": 45,  "W_sw": 10.0},
    {"name": "22nm",  "VDD": 0.8, "model": "ptm22hp.lib", "L_nm": 22,  "W_sw": 10.0},
]


def simulate_ron(node_cfg=None):
    """Run Ron comparison for one technology node using gds measurement."""
    if node_cfg is None:
        node_cfg = NODE_CONFIGS[0]

    node_name  = node_cfg["name"]
    VDD        = node_cfg["VDD"]
    model_path = spath(MODEL_DIR / node_cfg["model"])
    W_sw       = node_cfg["W_sw"]
    L_nm       = node_cfg.get("L_nm", L_NM_DEFAULT)
    W_cmos_p   = W_sw * 3.0   # 3× NMOS width to compensate µp < µn
    W_pmos_sw  = W_sw * 3.0   # same for standalone PMOS switch

    TCLK  = TCLK_DEFAULT
    FCLK  = FCLK_DEFAULT
    RON_TSTOP = RON_NCYC * TCLK

    print(f"\n  [{node_name}] Ron comparison ({RON_NCYC} cycles, VDD={VDD}V) ...", flush=True)
    t0 = time.perf_counter()

    dut_include, _ = render_dut(l_nm=L_nm, tag=node_name)

    tag   = f"bts_ron_{node_name}"
    paths = {k: LOG_DIR / f"{tag}_{k}.txt" for k in
             ("vin", "clk", "gds_n", "gds_p", "gds_cn", "gds_cp", "gds_bts")}

    kw = dict(
        VDD        = VDD,
        model_path = model_path,
        dut_include = dut_include,
        L          = f"{L_nm}n",
        W_sw       = W_sw,
        CS         = f"{CS_DEFAULT:.4e}",
        fclk_mhz   = FCLK / 1e6,
        tclk       = f"{TCLK:.4e}",
        t_high     = f"{TCLK/2:.4e}",
        node_name  = node_name,
        vin_lo     = f"{VDD * 0.005:.6f}",
        vin_hi     = f"{VDD * 0.995:.6f}",
        tstep      = f"{RON_TSTEP:.4e}",
        tstop      = f"{RON_TSTOP:.4e}",
        out_vin     = spath(paths["vin"]),
        out_clk     = spath(paths["clk"]),
        out_gds_n   = spath(paths["gds_n"]),
        out_gds_p   = spath(paths["gds_p"]),
        out_gds_cn  = spath(paths["gds_cn"]),
        out_gds_cp  = spath(paths["gds_cp"]),
        out_gds_bts = spath(paths["gds_bts"]),
    )

    log = LOG_DIR / f"{tag}.log"
    rc  = run_netlist("testbench_bts_ron.cir.tmpl", kw, log)
    elapsed = time.perf_counter() - t0
    print(f"  [{node_name}] exit {rc}, {elapsed:.1f}s", flush=True)

    def _load(key):
        p = paths[key]
        d = parse_wrdata(p) if p.exists() else None
        if d is not None:
            return d[:, 0], d[:, 1]   # (time_arr, value_arr)
        return None, None

    t_vin, vin      = _load("vin")
    t_clk, clk      = _load("clk")
    t_gn,  gds_n    = _load("gds_n")
    t_gp,  gds_p    = _load("gds_p")
    t_gcn, gds_cn   = _load("gds_cn")
    t_gcp, gds_cp   = _load("gds_cp")
    t_gb,  gds_bts  = _load("gds_bts")

    # CMOS gds = gds_n + gds_p (parallel), interpolated to common time base
    t = t_vin
    gds_cmos = None
    if gds_cn is not None and gds_cp is not None and t_gcn is not None:
        cn_interp = np.interp(t, t_gcn, gds_cn)
        cp_interp = np.interp(t, t_gcp, gds_cp)
        gds_cmos = cn_interp + cp_interp

    # Interpolate all gds arrays onto the vin time base
    def _interp(t_src, vals):
        if t_src is None or vals is None:
            return None
        return np.interp(t, t_src, vals)

    gds_n_i   = _interp(t_gn, gds_n)
    gds_p_i   = _interp(t_gp, gds_p)
    gds_bts_i = _interp(t_gb, gds_bts)
    clk_i     = np.interp(t, t_clk, clk) if t_clk is not None else clk

    ron_nmos, ron_pmos, ron_cmos, ron_bts, vin_pts = _extract_ron(
        t, vin, clk_i, gds_n_i, gds_p_i, gds_cmos, gds_bts_i, VDD, TCLK
    )

    p = circuit_params()
    p.update({"node_name": node_name, "VDD": VDD, "L_NM": L_nm,
               "W_sw": W_sw, "W_pmos_sw": W_pmos_sw, "W_cmos_p": W_cmos_p,
               "RON_NCYC": RON_NCYC})
    return {
        "node_name": node_name,
        "time": t, "vin": vin, "clk": clk,
        "ron_nmos": ron_nmos, "ron_pmos": ron_pmos,
        "ron_cmos": ron_cmos, "ron_bts":  ron_bts,
        "vin_pts":  vin_pts,
        "params": p,
        "rc": rc, "elapsed": elapsed,
    }


def _extract_ron(t, vin, clk, gds_n, gds_p, gds_cmos, gds_bts, VDD, TCLK):
    """
    Sample Ron = 1/gds at mid-sampling for each CLK cycle.
    Returns arrays of (ron_nmos, ron_pmos, ron_cmos, ron_bts, vin_pts).
    """
    if t is None or vin is None:
        return None, None, None, None, None

    clk_high = clk > VDD / 2
    edges    = np.where(np.diff(clk_high.astype(int)) > 0)[0]

    vin_pts  = []
    ron_nmos = []
    ron_pmos = []
    ron_cmos = []
    ron_bts  = []

    for edge_idx in edges:
        t_sample = t[edge_idx] + 0.5 * (TCLK / 2)  # 50% into high phase
        idx = np.searchsorted(t, t_sample)
        if idx >= len(t):
            continue

        v_in = vin[idx]
        if v_in < VDD * 0.01 or v_in > VDD * 0.99:
            continue

        vin_pts.append(v_in)

        def _ron(gds_arr):
            if gds_arr is None or idx >= len(gds_arr):
                return float("nan")
            g = gds_arr[idx]
            return 1.0 / g if g > 1e-9 else float("nan")

        ron_nmos.append(_ron(gds_n))
        ron_pmos.append(_ron(gds_p))
        ron_cmos.append(_ron(gds_cmos))
        ron_bts.append(_ron(gds_bts))

    def _arr(lst):
        return np.array(lst, dtype=float) if lst else None

    return _arr(ron_nmos), _arr(ron_pmos), _arr(ron_cmos), _arr(ron_bts), _arr(vin_pts)
