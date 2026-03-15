#!/usr/bin/env python3
"""
plot_noise_principle.py
=======================
Analytical (no simulation) figure explaining the comparator noise model.

Three panels (single row):
  1. Gaussian PDF — noise distribution at the decision point
  2. CDF (transfer curve) — P(output=1) vs Vin, for several σ values
  3. Offset illustration — CDF shifts left/right when µ ≠ 0

Called by run_tran_strongarm_comp.py (no arguments needed).
Output: WORK/plots/noise_principle.png
"""

import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from scipy.stats import norm

_ASSETS = Path(__file__).resolve().parent
sys.path.insert(0, str(_ASSETS))
from ngspice_common import PLOT_DIR

OUT_PNG = PLOT_DIR / "noise_principle.png"

# ── colour palette ─────────────────────────────────────────────────────────
C_BLUE   = "#1a7abf"
C_RED    = "#e65100"
C_GREEN  = "#2e7d32"
C_GREY   = "#757575"
C_YELLOW = "#f57f17"


def _cdf(vin, mu, sigma):
    return norm.cdf(vin, loc=mu, scale=sigma)


def _pdf(vin, mu, sigma):
    return norm.pdf(vin, loc=mu, scale=sigma)


def plot_noise_principle():
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        "Comparator Noise Model — Analytical (no simulation)\n"
        r"$P(\mathrm{out}=1) = \Phi\!\left(\frac{V_{in}-\mu}{\sigma}\right)$"
        r"    $\Rightarrow$    "
        r"$\sigma = k\,/\,\Phi^{-1}(P_1)$   [single-point probit]",
        fontsize=11, fontweight="bold",
    )

    # ── Panel 1: Gaussian PDF ──────────────────────────────────────────────
    ax = axes[0]
    sigma_ref = 350e-6   # V  (350 µV reference)
    mu_ref    = 0.0
    k_ref     = 350e-6   # = 1σ

    vin_v = np.linspace(-4 * sigma_ref, 4 * sigma_ref, 800)
    vin_uv = vin_v * 1e6

    pdf_vals = _pdf(vin_v, mu_ref, sigma_ref)

    # Fill area where Vdiff > k  → comparator outputs 1
    mask_above = vin_v >= k_ref
    mask_below = vin_v <= k_ref
    ax.fill_between(vin_uv, pdf_vals, where=mask_above,
                    alpha=0.30, color=C_BLUE, label=f"P(out=1) at k={k_ref*1e6:.0f}µV")
    ax.fill_between(vin_uv, pdf_vals, where=mask_below,
                    alpha=0.15, color=C_RED,  label="P(out=0)")
    ax.plot(vin_uv, pdf_vals, color=C_BLUE, lw=2)
    ax.axvline(0, color=C_GREY, lw=1.0, ls="--", label="µ = 0 (no offset)")
    ax.axvline(k_ref * 1e6, color=C_GREEN, lw=1.5, ls="-",
               label=f"k = {k_ref*1e6:.0f}µV (fixed input)")
    # Annotate σ as width
    ax.annotate("", xy=(sigma_ref * 1e6, _pdf(np.array([sigma_ref]), mu_ref, sigma_ref)[0] * 0.6),
                xytext=(0, _pdf(np.array([sigma_ref]), mu_ref, sigma_ref)[0] * 0.6),
                arrowprops=dict(arrowstyle="<->", color="k", lw=1.2))
    ax.text(sigma_ref * 1e6 / 2, _pdf(np.array([sigma_ref]), mu_ref, sigma_ref)[0] * 0.65,
            r"$\sigma$", ha="center", va="bottom", fontsize=11, color="k")
    ax.set_xlabel("Input differential  $V_{in}$  (µV)", fontsize=9)
    ax.set_ylabel("Probability density", fontsize=9)
    ax.set_title("Gaussian noise PDF at the decision point", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(vin_uv[0], vin_uv[-1])

    # ── Panel 2: CDF for different σ ──────────────────────────────────────
    ax = axes[1]
    sigma_vals = [150e-6, 350e-6, 700e-6]
    colors_sig  = [C_GREEN, C_BLUE, C_RED]
    vin_sweep = np.linspace(-1200e-6, 1200e-6, 800)
    vin_sweep_uv = vin_sweep * 1e6

    for sig, col in zip(sigma_vals, colors_sig):
        p1 = _cdf(vin_sweep, 0.0, sig)
        ax.plot(vin_sweep_uv, p1 * 100, color=col, lw=2,
                label=f"σ = {sig*1e6:.0f}µV")

    # Mark the probit extraction point for σ=350µV, k=350µV
    k_mark = 350e-6
    p1_mark = _cdf(k_mark, 0.0, 350e-6) * 100
    ax.plot(k_mark * 1e6, p1_mark, "o", ms=9, color=C_BLUE, zorder=5)
    ax.annotate(
        f"k={k_mark*1e6:.0f}µV → P(1)={p1_mark:.0f}%\n"
        r"$\sigma = k/\Phi^{-1}(P_1)$",
        xy=(k_mark * 1e6, p1_mark),
        xytext=(k_mark * 1e6 + 200, p1_mark - 12),
        fontsize=8, color=C_BLUE,
        arrowprops=dict(arrowstyle="->", color=C_BLUE, lw=1),
    )
    ax.axhline(50, color=C_GREY, lw=0.8, ls=":", label="50%")
    ax.fill_between(vin_sweep_uv, 65, 95, alpha=0.07, color=C_GREEN,
                    label="Ideal P(1) range [65%, 95%]")
    ax.set_xlabel("Input differential  $V_{in}$  (µV)", fontsize=9)
    ax.set_ylabel("P(output = 1)  (%)", fontsize=9)
    ax.set_title("Transfer curve: steeper = lower noise", fontsize=9)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)

    # ── Panel 3: Offset illustration ───────────────────────────────────────
    ax = axes[2]
    mu_vals    = [-150e-6, 0.0, 150e-6]
    mu_colors  = [C_RED, C_BLUE, C_GREEN]
    mu_labels  = ["µ = −150µV  (offset left)", "µ = 0  (ideal)", "µ = +150µV  (offset right)"]
    sigma_off  = 300e-6

    for mu, col, lbl in zip(mu_vals, mu_colors, mu_labels):
        p1 = _cdf(vin_sweep, mu, sigma_off)
        ax.plot(vin_sweep_uv, p1 * 100, color=col, lw=2, label=lbl)
        # Mark the 50% crossing (= offset)
        ax.axvline(mu * 1e6, color=col, lw=1.0, ls="--", alpha=0.6)

    ax.axhline(50, color=C_GREY, lw=1.0, ls=":", label="50% crossing = offset µ")
    ax.axvline(0, color=C_GREY, lw=0.8, ls="-", alpha=0.4)
    ax.set_xlabel("Input differential  $V_{in}$  (µV)", fontsize=9)
    ax.set_ylabel("P(output = 1)  (%)", fontsize=9)
    ax.set_title("Offset µ shifts the curve left/right\n"
                 "(50% crossing point = offset voltage)", fontsize=9)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    # Annotate: "Offset moves the crossing"
    ax.annotate("", xy=(150, 50), xytext=(-150, 50),
                arrowprops=dict(arrowstyle="<->", color="k", lw=1.5))
    ax.text(0, 53, "2 × |µ| = 300µV", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {OUT_PNG}")


if __name__ == "__main__":
    plot_noise_principle()
