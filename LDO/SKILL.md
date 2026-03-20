---
name: ldo
description: "PTM 180nm PMOS-pass LDO regulator simulation, sizing, and analysis skill. Use this skill whenever the user wants to: (1) simulate or re-run LDO DC/AC/noise/transient analyses in ngspice, (2) plot loop gain, PSRR, output impedance, load-step response, noise PSD, or transistor operating points, (3) compute or verify initial transistor sizing from specs (Vin, Vout, Iload, Cload, Vref), (4) iteratively adjust device sizes to meet specs (output accuracy ±1%, phase margin, PSRR, load/line regulation, noise, offset), (5) apply theoretical formulas for GBW, zero/pole frequencies, PSRR, load regulation, noise, or offset, (6) perform trade-off analysis between competing specs, (7) learn LDO topology, compensation theory, or sizing methodology. Technology: PTM 180nm BSIM3v3 (NMOS/PMOS, Lmin=180nm, Wmin=220nm, VDD up to 3.3V). Requires: ngspice on PATH, Python 3 + numpy/matplotlib/scipy."
---

# LDO Skill — PTM 180nm Low Dropout Regulator

**Technology**: PTM 180nm, BSIM3v3 Level 8 (NMOS / PMOS), Lmin = 180 nm, Wmin = 220 nm.
**Dependencies**: `ngspice` on PATH, Python 3 + `numpy`, `matplotlib`, `scipy`.

---

## Layout

```
LDO/
├── SKILL.md
├── scripts/                        ← run from here (cd LDO/scripts)
│   ├── ngspice_common.py           — paths, ngspice runner, parser, template renderer
│   ├── ldo_common.py               — circuit params, DUT rendering, cap/resistance helpers
│   │
│   ├── simulate_ldo_dc.py          — backend: line & load regulation
│   ├── simulate_ldo_ac.py          — backend: loop gain, PSRR, Zout
│   ├── simulate_ldo_noise.py       — backend: output noise PSD, 1/f corner, Vn_rms
│   ├── simulate_ldo_tran.py        — backend: load-step transient, V_drop, t_rec
│   ├── simulate_ldo_op.py          — backend: transistor op-points (gm/ID methodology)
│   │
│   ├── plot_ldo_dc.py              — plot: line & load regulation curves
│   ├── plot_ldo_ac.py              — plot: PSRR, Zout, loop gain (Bode)
│   ├── plot_ldo_noise.py           — plot: noise PSD with 1/f corner annotation
│   ├── plot_ldo_tran.py            — plot: VOUT load-step waveform
│   ├── plot_ldo_op.py              — plot: gm/ID, gm·ro, fT bar charts
│   │
│   ├── run_ldo.py                  ← MAIN entry (DC+AC+noise+tran in parallel, then OP)
│   ├── run_ldo_dc.py               — standalone: DC only
│   ├── run_ldo_ac.py               — standalone: AC only
│   ├── run_ldo_noise.py            — standalone: noise only
│   ├── run_ldo_tran.py             — standalone: transient only
│   │
│   ├── run_rcomp_sweep.py          — sweep R_COMP → PM, GBW
│   ├── run_ccomp_sweep.py          — sweep C_COMP → PM, GBW
│   ├── run_cout_sweep.py           — sweep C_OUT  → PM, GBW
│   ├── run_error_amp_design.py     — gm/ID-based error-amp sizing script
│   └── run_auto_design.py          — automated design iteration loop
│
├── assets/
│   ├── netlist/                    ← SPICE templates (*.cir.tmpl)
│   └── models/ptm180.lib           ← PTM 180nm BSIM3v3 (NMOS / PMOS)
│
└── references/                     ← read for theory / design guidance
    ├── 01_topology.md
    ├── 02_stability.md
    ├── 03_psrr.md
    ├── 04_noise.md
    └── model_params.md
```

All generated files (logs, plots, netlists) go to `WORK/` at the repo root.
Override with env-var `ANALOG_WORK_DIR`.

---

## Task → Script Decision Guide

| User asks about | Action |
|-----------------|--------|
| Full simulation (all specs) | `run_ldo.py` |
| DC only (line/load regulation) | `run_ldo_dc.py` |
| AC only (loop gain, PSRR, Zout) | `run_ldo_ac.py` |
| Noise only | `run_ldo_noise.py` |
| Transient load step only | `run_ldo_tran.py` |
| Transistor op-points | `simulate_ldo_op.simulate_op()` |
| Phase margin vs R_COMP | `run_rcomp_sweep.py` |
| Phase margin vs C_COMP | `run_ccomp_sweep.py` |
| Phase margin vs C_OUT | `run_cout_sweep.py` |
| gm/ID-based error-amp sizing | `run_error_amp_design.py` |
| Initial sizing from specs | Apply **Initial Sizing** section below, then edit `ldo_common.py` |
| Topology / compensation theory | Read `references/01_topology.md`, `02_stability.md` |
| PSRR theory | Read `references/03_psrr.md` |
| Noise theory | Read `references/04_noise.md` |
| Model parameters | Read `references/model_params.md` |

---

## Running

```bash
cd LDO/scripts
python run_ldo.py          # All analyses in parallel (~10 s)
```

Key outputs in `WORK/`:

| File | Contents |
|------|----------|
| `plots/ldo_dc.png` | Line & load regulation curves |
| `plots/ldo_ac.png` | Loop gain (Bode), PSRR, Zout |
| `plots/ldo_noise.png` | Output noise PSD, 1/f corner |
| `plots/ldo_tran.png` | Load-step VOUT waveform |
| `plots/ldo_op.png` | gm/ID, gm·ro, fT bar charts |
| `logs/ldo_report.txt` | Consolidated numeric metrics |

---

## Circuit Topology

PMOS-pass LDO with Miller-compensated two-stage error amplifier.

```
VIN ──► M2 (pass, PMOS) ──────────────────────────► VOUT
              ▲ gate=net3                              │
              │                                  R0 (R_FB_TOP)
         ┌────┴───────────────────────────┐           │
         │      Error Amplifier           │      net30 (V_fb)
         │                                │           │
         │  M3/M4 (PMOS current mirror)   │      R1 (R_FB_BOT)
         │     ▲             ▲            │           │
         │   M0(VREF)    M1(V_fb)  ←──── ┘          GND
         │   NMOS diff pair (non-inv / inv)
         │        │
         │   M5 (tail mirror, 10×) ─── M6 (diode ref, 1×) ←── I_bias
         └────────────────────────────────────────────────────────────
Compensation: R2 (R_COMP) + C0 (C_COMP) from net3 → VOUT
  → introduces left-half-plane zero: fz = 1/(2π·R2·C0)
Bypass: C1 (large, ≈1F) on ibias node; C2 (C_OUT) on VOUT
```

**Topology constraints**:
- M0 = M1 (identical sizes — matched differential pair)
- M3 = M4 (identical sizes — matched current mirror load)
- M5 / M6: same L, W_M5 = N × W_M6 (mirror ratio N, default N = 10)

**Editable globals**: all in `LDO/scripts/ldo_common.py`.

---

## Initial Sizing from Specs

Given user inputs: **Vref**, **Vin**, **Vout**, **Iload**, **Cload** (default 1 µF).

### Step 1 — Feedback Resistors R0, R1

From regulation condition `Vout = Vref × (R0 + R1) / R1`:

```
R0 / R1 = Vout/Vref − 1

Select I_div = 1% × Iload   (current through divider)
→ R0 + R1 = Vout / I_div = Vout × 100 / Iload
→ R1 = Vref / I_div
→ R0 = (Vout − Vref) / I_div
```

### Step 2 — Pass Transistor M2 (PMOS)

M2 must supply full Iload. Start with minimum L for low Vdrop:

| Parameter | Value |
|-----------|-------|
| L | Lmin = 180 nm |
| W per finger | 10 × Wmin = 2.2 µm |
| fingers | 10 |
| multiplier | 100 |

Total W = 10 × 10 × 100 × Wmin = 22 mm.
**DC iteration rule** (see Step 7): adjust multiplier to achieve Vout accuracy ±1%.

### Step 3 — Bias Current Mirror M5 / M6 (NMOS)

```
Ibias = Iload / 1000          (e.g. 100 µA for Iload = 100 mA)
I_tail = Ibias × N_mirror     (default N = 10, so I_tail = Iload/100)
```

| Parameter | M6 (ref, 1×) | M5 (mirror, 10×) |
|-----------|-------------|-----------------|
| L | 5 × Lmin = 900 nm | same as M6 |
| W per finger | 10 × Wmin = 2.2 µm | same as M6 |
| fingers | 8 | 8 |
| multiplier | 1 | 10 |

Large L reduces current mismatch (ΔI/I ∝ 1/L for channel-length modulation).
Bypass capacitor on ibias node: **C1 = 1 F** (large ideal cap, suppresses AC ripple).

### Step 4 — Differential Pair M0 / M1 (NMOS, matched)

Long L for high intrinsic gain (gm·ro) and good matching:

| Parameter | Value |
|-----------|-------|
| L | 2 × Lmin = 360 nm |
| W per finger | Wmin = 0.22 µm |
| fingers | 8 |
| multiplier | 10 |

### Step 5 — Current Mirror Load M3 / M4 (PMOS, matched)

Very long L for high ro (high Av1) and good matching:

| Parameter | Value |
|-----------|-------|
| L | 4 × Lmin = 720 nm |
| W per finger | 2 × Wmin = 0.44 µm |
| fingers | 8 |
| multiplier | 10 |

### Step 6 — Compensation Network

```
Cc = Cload / 5000              (initial value; adjust for stability)
Rz: choose so that ωz ≈ GBW  (see Stability section below)
```

Set `C_COMP = Cc`, `R_COMP = Rz` in `ldo_common.py`.

### Step 7 — DC Output Voltage Accuracy Check (iterate)

Run `python run_ldo_dc.py`. Requirement: **|Vout_sim − Vout_target| / Vout_target ≤ 1%**.

| Condition | Action |
|-----------|--------|
| Vout_sim < 0.99 × Vout_target | Increase M2 fingers (more current drive) |
| Vout_sim > 1.01 × Vout_target | Decrease M2 fingers (less current drive) |

---

## Theoretical Formulas

### Key Small-Signal Quantities

```
β  = R1 / (R0 + R1) = Vref / Vout      (feedback factor)
Av1 = gm1 × (ro1 ∥ ro3)                (error-amp DC gain)
gm  = √(2 · µ · Cox · W/L · Id)        → adjust mainly via W; L if needed
ro  ∝ 1 / (λ · Id)                     → adjust via L (longer L → larger ro)
```

### Closed-Loop Specs

**Loop Gain (DC)**:
```
T0 = β × Av1 × gm2 × ro2
```

**GBW (Gain-Bandwidth Product)**:
```
GBW ≈ β × gm1 / Cc
```

**Load Regulation** (output impedance at low freq):
```
Zout(s) ≈ (1 + s·Cc·(ro1∥ro3)) / (β · Av1 · gm2)
```

**PSRR** (supply rejection):
```
PSRR(s) ≈ [gm2·(ro1∥ro3)·s·Cc + 1/ro2] / (β · Av1 · gm2)
```

### Poles and Zero

| Frequency | Expression | Tuning |
|-----------|-----------|--------|
| ωp1 (dominant) | ≈ 1 / (T0 · ro2 · CL) | set by CL and loop gain |
| ωp2 (output) | ≈ gm2 / CL | ↑gm2 or ↓CL to push out |
| ωz (compensation zero) | ≈ −1 / [(Rz − 1/gm2) · Cc] | set Rz to place ωz ≈ GBW |
| ωp3 (parasitic) | ≈ −1 / (Rz · CS) | target ωp3 ≥ 2 × GBW |

where `CS = (Cn·Cc·CL) / (Cn·Cc + Cn·CL + Cc·CL)`, Cn = gate cap of M2.

**Stability target**: ωz ≈ GBW and ωp3 ≥ 2 × GBW.

### Noise (Output-Referred)

**Thermal noise**:
```
Vn²_out = (1/β²) × [4kT(R0∥R1) + 8kTγ·(gm1 + gm4) / gm1²]
```

**1/f (flicker) noise** (dominant at low frequency):
```
Vn²_out = (2K / β²·Cox·f) × [1/(W1·L1) + (1/(W4·L4))·(gm4/gm1)²]
         ≈ (2K / β²·Cox·f) × [1/(W1·L1) + µp·L1/(µn·W1·L4²)]
```

Low-frequency: 1/f noise dominates.
High-frequency: thermal noise dominates; compare relative magnitudes.

---

## Spec Optimization Guide

### Output Voltage Accuracy (±1%)

Primary knob: **M2 multiplier** (fingers).

| Vout too low | Increase M2 multiplier |
|---|---|
| Vout too high | Decrease M2 multiplier |

Re-run `run_ldo_dc.py` after each change.

---

### Load Regulation

`Zout(s) ≈ (1 + s·Cc·(ro1∥ro3)) / (β · Av1 · gm2)`

| Frequency | Primary actions | Secondary |
|-----------|----------------|-----------|
| Low freq | ↑Av1 (↑W1 or ↓L1); ↑gm2 (↑W2 or ↓L2) | — |
| High freq | ↑gm1 (↑W1); ↑gm2 (↑W2 or ↓L2); ↓Cc | — |

---

### Line Regulation

| Frequency | Primary actions | Secondary |
|-----------|----------------|-----------|
| Low freq | ↑Av1 (↑W1 or ↓L1); ↑gm2·ro2 (↑W2 or ↓L2) | ↑gm3 (↑W3); ↑ro5 (↓L5/L6) |
| High freq | ↑gm1 (↑W1); ↓Cc | — |

---

### Phase Margin (Stability)

**Target**: PM ≥ 45° (≥ 60° recommended). Tune ωz and ωp3.

**Reading the Bode plot** (loop gain phase vs frequency):
- Phase has a gradual slope ("缓坡") region caused by ωz.
- ωz should align with the GBW crossing.
  - Cue: if the slope ends at too high a frequency → **increase Rz**.
  - Cue: if the slope ends at too low a frequency → **decrease Rz**.

| Action | Effect |
|--------|--------|
| Adjust Rz (primary) | Move ωz to ≈ GBW |
| ↓ Cgg_M2 = reduce W2 and L2 proportionally | Push ωp3 higher |
| ↓ W1 (↓gm1) | ↓GBW → more margin, at cost of regulation bandwidth |
| ↑ Cc (secondary) | ↓GBW → more margin; degrades PSRR and load regulation |

---

### PSRR

`PSRR ≈ [gm2·(ro1∥ro3)·s·Cc + 1/ro2] / (β · Av1 · gm2)`

| Action | Effect |
|--------|--------|
| ↑ Av1 (↑W1 or ↓L1) | ↑ DC PSRR |
| ↑ gm2 (↑W2) | ↑ DC PSRR |
| ↑ ro2 (↑L2) | ↑ DC PSRR |
| ↑ Cc | ↑ high-freq PSRR (but ↓ load regulation at high freq) |

---

### Noise

| Frequency | Primary actions |
|-----------|----------------|
| Low freq (1/f) | ↑ W1 (best with L1 also ↑ proportionally); ↑ L4 |
| High freq (thermal) | ↑ gm1 (↑W1); ↓ gm4 (↓W4 or ↑L4) |

---

### Offset

| Mismatch source | Mitigation |
|-----------------|-----------|
| Diff pair M0/M1 | ↑ W1 (area ↑) |
| Current mirror M3/M4 | ↑ L4 (channel-length modulation mismatch ↓) |
| Feedback resistors R0/R1 | Increase resistor area (wider, longer poly) |

Primary rule: **↑W1 and ↑L4** simultaneously reduce both offset and noise.

---

## Trade-off Analysis

Inspect simulation results: identify which spec has the **least margin** (closest to failing) and which has **excess margin** before adjusting.

| Adjustment | ✓ Improves | ✗ Degrades |
|-----------|-----------|-----------|
| ↑ W1 (diff pair wider) | Load reg (LF/HF), Line reg, PSRR, Noise, Offset | PM (GBW↑ → less phase) |
| ↓ L1 (diff pair shorter) | gm1↑, Load reg (LF), Line reg (LF) | gm·ro↓ (Av1↓), Noise (1/f↑), Offset |
| ↑ W2 (pass transistor wider) | Output accuracy, Load/Line reg, PSRR | ωp3↓ (Cgg2↑ → PM↓) |
| ↓ W2 & ↓ L2 (same ratio) | ωp3↑ (PM↑) | gm2↓ (regulation↓) |
| ↑ L4 (load mirror longer) | Av1↑, Noise (1/f↓), Offset, PSRR | Speed (ro4↑ but slower pole) |
| ↑ Cc | PM (GBW↓) | PSRR (↓), Load reg (HF↓) |
| ↓ Cc | PSRR, Load reg (HF) | PM↓ |
| ↑ Rz | ωz↑ → adjust PM | ωp3↓ (CS path) |
| ↓ Rz | ωp3↑ | ωz↓ → may lose PM correction |

**Decision workflow**:
1. Run `run_ldo.py`, read `ldo_report.txt`.
2. List all specs with margin sign and magnitude.
3. Pick the worst (most over-spec or most under-margin).
4. Choose the adjustment that fixes it without pushing a near-failing spec into failure.
5. Re-run and iterate.

---

## Transistor Size Variables (ldo_common.py)

| Variable | Device | Meaning |
|----------|--------|---------|
| `W_M2_UM`, `L_M2_NM`, `M_M2` | M2 pass | W/finger [µm], L [nm], multiplier |
| `W_M0_UM`, `L_M0_NM`, `M_M0` | M0 diff (+) | same convention |
| `W_M1_UM`, `L_M1_NM`, `M_M1` | M1 diff (−) | keep = M0 |
| `W_M3_UM`, `L_M3_NM`, `M_M3` | M3 load (out) | keep = M4 |
| `W_M4_UM`, `L_M4_NM`, `M_M4` | M4 load (diode) | keep = M3 |
| `W_M5_UM`, `L_M5_NM`, `M_M5` | M5 tail mirror | keep L = L_M6 |
| `W_M6_UM`, `L_M6_NM`, `M_M6` | M6 bias ref | M6 mult = 1 always |
| `R_FB_TOP` | R0 | top feedback resistor [Ω] |
| `R_FB_BOT` | R1 | bottom feedback resistor [Ω] |
| `R_COMP` | Rz | compensation zero resistor [Ω] |
| `C_COMP` | Cc | compensation capacitor [F] |
| `C_OUT` | CL | output decoupling capacitor [F] |
| `IBIAS_UA` | I1 | bias current source [µA] |

---

## Output File Conventions

- **All outputs to `WORK/`** — never inside the skill package.
- **Matplotlib `Agg` backend** — never pop up figures; always `plt.close(fig)` after `savefig()`.
- **Forward slashes** in ngspice paths (`spath()` helper).
- **Parallel execution** via `ThreadPoolExecutor` for independent simulations.
- **Max 3 vertically stacked subplots** per figure.

---

## References

| File | Topic |
|------|-------|
| `references/01_topology.md` | Circuit topology, feedback loop, compensation |
| `references/02_stability.md` | Pole-zero analysis, PM, Bode plot reading |
| `references/03_psrr.md` | PSRR mechanism, frequency dependence |
| `references/04_noise.md` | Thermal & 1/f noise models, optimization |
| `references/model_params.md` | PTM 180nm BSIM3v3 parameters (vth0, Cox, u0 …) |
