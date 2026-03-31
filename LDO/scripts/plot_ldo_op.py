#!/usr/bin/env python3
"""
plot_ldo_op.py
==============
Transistor operating-point visualisation using gm/ID methodology.

Three panels:
  1. gm/ID bar chart with inversion-region bands
  2. gm*ro intrinsic gain bars
  3. fT transit frequency bars

Saved to WORK/plots/ldo_op.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from ngspice_common import PLOT_DIR

OP_PNG = PLOT_DIR / "ldo_op.png"

# Colour palette consistent with other LDO plots
_CMAP = {
    'nmos': '#1a7abf',
    'pmos': '#e84141',
    'band_wi':   '#f0f8e8',   # weak inversion band
    'band_mod':  '#fff8e8',   # moderate inversion band
    'band_si':   '#f8f0ff',   # strong inversion band
    'grid':      '#cccccc',
}

# gm/ID region boundaries (approximate, BSIM3 180nm)
GMID_WI_HI   = 28.0   # above: subthreshold / weak inversion
GMID_MOD_LO  = 10.0   # 10-28: moderate inversion
GMID_SI_LO   =  5.0   # below 10: strong inversion


def plot_op(results):
    """Visualise per-transistor gm/ID, gm*ro, fT as grouped bars."""
    transistors = results.get("transistors", [])
    params      = results.get("params", {})

    # Filter to devices with valid data
    devs = [t for t in transistors if t.get("gm") is not None]
    if not devs:
        _plot_no_data(params)
        return

    names   = [t['name'].upper() for t in devs]
    roles   = [t['role']         for t in devs]
    pols    = [t['pol']          for t in devs]
    gmids   = [t.get('gmid',  0) for t in devs]
    gmros   = [t.get('gmro',  0) for t in devs]
    fts_mhz = [t.get('ft_Hz', 0) / 1e6 for t in devs]
    ids_ua  = [abs(t.get('id', 0)) * 1e6 for t in devs]

    n = len(devs)
    x = np.arange(n)
    colors = [_CMAP['nmos'] if p == 'nmos' else _CMAP['pmos'] for p in pols]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    vin = params.get('VIN_NOM', '?')
    fig.suptitle(
        f"PTM 180nm LDO — Transistor Operating Points (gm/ID Methodology)\n"
        f"VIN={vin}V, VOUT~1.8V, ILOAD=100mA nominal",
        fontsize=11,
    )

    # ── Panel 0: gm/ID ────────────────────────────────────────────────────────
    ax = axes[0]
    bars = ax.bar(x, gmids, color=colors, edgecolor='white', linewidth=0.8,
                  zorder=3)

    # Inversion region bands
    xmin, xmax = -0.5, n - 0.5
    ax.axhspan(GMID_WI_HI, 35,         facecolor=_CMAP['band_wi'],  alpha=0.7, zorder=1)
    ax.axhspan(GMID_MOD_LO, GMID_WI_HI, facecolor=_CMAP['band_mod'], alpha=0.7, zorder=1)
    ax.axhspan(0,           GMID_MOD_LO, facecolor=_CMAP['band_si'],  alpha=0.7, zorder=1)

    # Region labels
    ax.text(n - 0.52, 31,               'Weak inv.',     fontsize=7.5, color='#447744', ha='right')
    ax.text(n - 0.52, (GMID_MOD_LO + GMID_WI_HI) / 2, 'Moderate', fontsize=7.5, color='#887700', ha='right')
    ax.text(n - 0.52, GMID_SI_LO / 2 + 1.5, 'Strong inv.', fontsize=7.5, color='#664488', ha='right')

    # Value labels on bars
    for bar, v in zip(bars, gmids):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
                f'{v:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f'{n}\n({r[:10]})' for n, r in zip(names, [t['role'] for t in devs])],
        fontsize=7.5)
    ax.set_ylabel('gm/ID  (V$^{-1}$)', fontsize=10)
    ax.set_title('gm/ID  [design efficiency]', fontsize=10)
    ax.set_ylim(0, 35)
    ax.grid(axis='y', color=_CMAP['grid'], linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)

    # Legend: NMOS / PMOS
    patch_n = mpatches.Patch(color=_CMAP['nmos'], label='NMOS')
    patch_p = mpatches.Patch(color=_CMAP['pmos'], label='PMOS')
    ax.legend(handles=[patch_n, patch_p], fontsize=8, loc='upper right')

    # ── Panel 1: gm*ro ────────────────────────────────────────────────────────
    ax = axes[1]
    bars2 = ax.bar(x, gmros, color=colors, edgecolor='white', linewidth=0.8,
                   zorder=3)
    for bar, v in zip(bars2, gmros):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f'{v:.0f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Annotate Id on secondary info
    for i, (dev, id_ua) in enumerate(zip(devs, ids_ua)):
        ax.text(i, 8, f'{id_ua:.0f}µA' if id_ua < 1000 else f'{id_ua/1e3:.1f}mA',
                ha='center', va='bottom', fontsize=7, color='#555555')

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f'{n}\n({r[:10]})' for n, r in zip(names, [t['role'] for t in devs])],
        fontsize=7.5)
    ax.set_ylabel('gm * ro  (intrinsic gain)', fontsize=10)
    ax.set_title('gm*ro  [intrinsic gain]', fontsize=10)
    ax.grid(axis='y', color=_CMAP['grid'], linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    # Reference line: minimum useful gain for a stage
    ax.axhline(20, color='#888888', lw=0.8, ls='--', label='gm*ro = 20')
    ax.legend(fontsize=8)

    # ── Panel 2: fT ───────────────────────────────────────────────────────────
    ax = axes[2]
    # Use log scale for fT since M2 pass transistor is GHz-range
    bars3 = ax.bar(x, fts_mhz, color=colors, edgecolor='white', linewidth=0.8,
                   zorder=3)
    for bar, v in zip(bars3, fts_mhz):
        label = f'{v:.0f}' if v >= 100 else f'{v:.1f}'
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.05,
                label, ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f'{n}\n({r[:10]})' for n, r in zip(names, [t['role'] for t in devs])],
        fontsize=7.5)
    ax.set_ylabel('fT  (MHz)', fontsize=10)
    ax.set_title('fT  [transit frequency, analytical Cgg]', fontsize=10)
    ax.set_yscale('log')
    ax.grid(axis='y', color=_CMAP['grid'], linewidth=0.5, which='both', zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OP_PNG, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved -> {OP_PNG.name}")


def _plot_no_data(params):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, "No transistor operating-point data",
            ha='center', va='center', transform=ax.transAxes, fontsize=12)
    fig.savefig(OP_PNG, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved -> {OP_PNG.name}")
