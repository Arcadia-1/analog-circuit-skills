---
name: two_stage_opamp
description: "Two-stage CMOS operational amplifier simulation skill. Use when the user wants to simulate or size a Miller-compensated two-stage op amp with PMOS differential input pair, NMOS current-mirror first-stage load, NMOS common-source second stage, PMOS current-source load, bias mirror, Cc compensation, and CL load. Supports ngspice DC operating point, AC gain/phase sweep, pole-zero analysis, and output-noise analysis."
---

# Two-Stage Op Amp Skill

Miller-compensated two-stage CMOS op amp using PTM 180nm models.

## Topology

```text
M7 + Ibias -> PMOS bias mirror
M5        -> first-stage PMOS tail current source
M0, M1    -> PMOS differential input pair
M3, M4    -> NMOS current-mirror active load
M2        -> NMOS common-source second stage
M6        -> PMOS current-source second-stage load
Cc        -> Miller compensation from first-stage output to Vout
CL        -> output load capacitor
```

Ports: `INP`, `INN`, `OUT`, `VDD`, `VSS`.

## Running

```bash
cd two_stage_opamp/scripts
python run_opamp.py
```

This runs:

- DC operating point and basic bias currents.
- AC open-loop gain and phase versus frequency.
- Pole-zero extraction for dominant pole, non-dominant pole, and zeros.
- Output-referred noise density and integrated RMS noise.

Outputs go to `WORK/plots`, `WORK/logs`, and `WORK/netlists`.

## Main Scripts

| Task | Script |
|------|--------|
| Full simulation | `run_opamp.py` |
| DC operating point | `run_opamp_dc.py` |
| AC gain/phase | `run_opamp_ac.py` |
| Pole-zero | `run_opamp_pz.py` |
| Noise only | `run_opamp_noise.py` |

## Design Knobs

Edit `scripts/opamp_common.py`:

- `IBIAS` controls the PMOS bias mirror current.
- `CC` and `CL` set Miller compensation and output loading. The default `CC=12pF` is intentionally conservative so the extracted non-dominant pole and first RHP zero clear the GBW-ratio checks.
- `W_M0_M1_UM`, `W_M2_UM`, `W_M3_M4_UM`, `W_M5_M7_UM`, `W_M6_UM` set transistor widths.
- `VCM` sets input common-mode voltage.
