#!/usr/bin/env python3
"""plot_ldo_noise.py -- output noise PSD: V(vout, vss)."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ngspice_common import PLOT_DIR

NOISE_PNG = PLOT_DIR / "ldo_noise.png"

C_ON  = "#1a7abf"
C_REF = "#888888"


def plot_noise(results):
    """Single-panel output noise density plot."""
    onoise  = results.get("onoise", {})
    metrics = results.get("metrics", {})
    params  = results.get("params", {})

    fig, ax = plt.subplots(figsize=(8, 5))

    vn_1k  = metrics.get("vn_1k_nvrtHz", float("nan"))
    vn_10k = metrics.get("vn_10k_nvrtHz", float("nan"))
    vn_rms = metrics.get("vn_rms_uv",    float("nan"))
    corner = metrics.get("flicker_corner_hz", float("nan"))

    f_lo = params.get("F_INTEG_LO", 10)
    f_hi = params.get("F_INTEG_HI", 100e3)

    title_parts = [f"VIN={params.get('VIN_NOM','?')}V, VOUT={params.get('VOUT_NOM','?')}V"]
    if not np.isnan(vn_1k):
        title_parts.append(f"Vn@1kHz={vn_1k:.1f} nV/rtHz")
    if not np.isnan(vn_rms):
        title_parts.append(f"Vn_rms={vn_rms:.2f} uV ({f_lo:.0f}Hz-{f_hi/1e3:.0f}kHz)")
    if not np.isnan(corner):
        title_parts.append(f"1/f corner={corner:.0f} Hz")
    fig.suptitle("PTM 180nm LDO — Output Noise  V(vout, vss)\n" +
                 "  |  ".join(title_parts), fontsize=11)

    freq = onoise.get("freq")
    psd  = onoise.get("psd")
    if freq is not None and psd is not None:
        vn = np.abs(psd) * 1e9   # nV/sqrt(Hz)  (psd already V/rtHz from ngspice)
        ax.semilogx(freq, vn, color=C_ON, lw=2, label="Output noise  V(vout, vss)")

        # Thermal noise floor line
        vn_floor = metrics.get("vn_floor_nvrtHz", float("nan"))
        if not np.isnan(vn_floor):
            ax.axhline(vn_floor, color=C_REF, lw=1.0, ls="--",
                       label=f"Thermal floor ~{vn_floor:.1f} nV/rtHz")

        # 1/f corner marker
        corner = metrics.get("flicker_corner_hz", float("nan"))
        if not np.isnan(corner):
            ax.axvline(corner, color="#e07b00", lw=1.0, ls=":",
                       label=f"1/f corner ~{corner:.0f} Hz")

        # Spot-noise markers at 1 kHz and 100 kHz
        for f_spot in [1e3, 100e3]:
            if freq[0] <= f_spot <= freq[-1]:
                vn_spot = float(np.interp(f_spot, freq, vn))
                f_str = f"{int(f_spot / 1e3)} kHz"
                ax.plot(f_spot, vn_spot, "o", color=C_ON, ms=5)
                ax.annotate(
                    f"({f_str}, {vn_spot:.1f} nV/rtHz)",
                    xy=(f_spot, vn_spot),
                    xytext=(f_spot * 2.5, vn_spot * 1.3),
                    fontsize=8, color=C_ON,
                    arrowprops=dict(arrowstyle="-", color=C_ON, lw=0.7, alpha=0.5),
                )

        # Integration band shading
        if not np.isnan(vn_rms):
            mask = (freq >= f_lo) & (freq <= f_hi)
            if mask.sum() > 1:
                ax.fill_between(freq[mask], vn[mask], alpha=0.12, color=C_ON,
                                label=f"Integration band ({f_lo:.0f}Hz-{f_hi/1e3:.0f}kHz)")

        ax.set_xlabel("Frequency (Hz)", fontsize=10)
        ax.set_ylabel("Output Noise Density (nV/rtHz)", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, which="both", alpha=0.25)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(NOISE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {NOISE_PNG.name}")
