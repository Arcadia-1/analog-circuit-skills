---
name: bootstrap_switch
description: "Bootstrapped sampling switch simulation and analysis skill for SAR ADC design. Use when the user wants to: (1) simulate a bootstrap switch with ngspice (180nm PTM, VDD=1.8V), (2) verify the bootstrap mechanism — gate voltage tracks Vin+VDD, (3) compare on-resistance (Ron) of NMOS vs CMOS vs bootstrap switch across input range, (4) study clock feedthrough and charge injection effects, (5) understand the bootstrap switch circuit topology, working phases, or transistor roles, (6) size transistors for a bootstrap switch (sampling switch W, bootstrap capacitor CB). Requires: ngspice skill installed, Python 3 with numpy/matplotlib."
---

# Bootstrap Switch Skill

**Dependencies**: `ngspice` skill (installed), Python 3 + `numpy`, `matplotlib`.

## Asset Layout

```
assets/
├── bootstrap_common.py             — shared parameters, DUT rendering, helpers
├── netlist/
│   ├── bootstrap_switch.cir.tmpl   — DUT: .subckt bootstrap_switch (parameterized W, L, CB)
│   ├── testbench_bts_tran.cir.tmpl — TB: transient waveform (CLK, VIN, VGATE, VSAMPLED)
│   └── testbench_bts_ron.cir.tmpl  — TB: Ron vs Vin comparison (NMOS / CMOS / bootstrap)
├── simulate_tran_bts_wave.py       — waveform simulation
├── simulate_tran_bts_ron.py        — Ron sweep simulation
├── plot_tran_bts_wave.py           — waveform figure (3 panels)
├── plot_tran_bts_ron.py            — Ron comparison figure
├── run_tran_bts_wave.py            — entry point: waveform only
├── run_tran_bts_ron.py             — entry point: Ron sweep only
└── run_tran_bts.py                 — entry point: all simulations
```

## Running

```bash
cd bootstrap_switch/assets
python run_tran_bts.py          # All simulations (~10s)
python run_tran_bts_wave.py     # Waveform only
python run_tran_bts_ron.py      # Ron comparison only
```

Outputs go to `WORK/` at repo root (logs → `WORK/logs/`, plots → `WORK/plots/`).

## Circuit Topology

Classic bootstrapped NMOS sampling switch, 180nm PTM, VDD=1.8V.

The circuit has 3 functional blocks: an inverter (CLKS→CLKSB), the bootstrapper
(charge pump that produces VGATE = VIN + VDD), and the sampling switch MS.

```
Transistor  Type   Gate     Drain    Source   Role
─────────────────────────────────────────────────────────────────────
MS          NMOS   VGATE    VOUT     VIN      Sampling switch (main)
M1          PMOS   VGATE    CB_TOP   VDD      Reset: charges CB to VDD
M2          NMOS   CLKSB    GND      CB_BOT   Reset: discharges CB bottom
M3          NMOS   VGATE    CB_BOT   VIN      Sampling: connects VIN to CB bottom
M4          PMOS   NET_G4   VGATE    CB_TOP   Sampling: connects CB top to VGATE
M4A         NMOS   VGATE    NET_G4   VIN      Sampling: drives M4 gate to VIN
M4B         PMOS   CLKS     NET_G4   VDD      Reset: drives M4 gate to VDD
M4C         NMOS   CLKS     NET_G4   CB_BOT   Startup: pulls M4 gate low at CLK edge
M5          NMOS   CLKSB    GND      NET_5A   Reset: pulls VGATE toward GND
M5A         NMOS   VDD      NET_5A   VGATE    Cascode: protects M5 from VDD+VIN
MP_INV      PMOS   CLKS     CLKSB    VDD      Inverter PMOS
MN_INV      NMOS   CLKS     CLKSB    GND      Inverter NMOS
```

### Operating Phases

**Reset (CLKS=0, CLKSB=1):**
- M1 ON → charges CB top plate to VDD
- M2 ON → discharges CB bottom plate to GND
- M5+M5A ON → pulls VGATE to GND → MS OFF (switch open)
- M4B ON → pre-charges M4 gate to VDD (prepares M4 to be OFF)

**Sampling (CLKS=1, CLKSB=0):**
- M3 ON → connects VIN to CB bottom plate
- CB bottom = VIN, CB holds VDD → CB top = VIN + VDD
- M4C assists startup → pulls M4 gate low → M4 turns ON
- M4 ON → connects CB top (VIN+VDD) to VGATE
- M4A ON → connects VIN to M4 gate (takes over from M4C)
- MS: Vgs = VGATE − VIN = VDD (constant!) → switch ON

**Key insight:** MS always sees Vgs = VDD regardless of VIN, giving
signal-independent on-resistance — essential for >8-bit sampling linearity.

## Transistor Sizes (all L = 180 nm)

| Device | W (µm) | Description |
|--------|--------|-------------|
| MS (sampling) | 10.0 | Main switch — wider = lower Ron |
| M1 (reset CB) | 3.0 | PMOS, charges CB top |
| M2 (reset CB bot) | 1.0 | NMOS, discharges CB bottom |
| M3 (VIN to CB bot) | 1.0 | NMOS, connects VIN to CB bottom |
| M4 (CB top to VGATE) | 3.0 | PMOS, top-plate conduction |
| M4A (VIN to M4 gate) | 1.0 | NMOS, drives M4 gate |
| M4B (VDD to M4 gate) | 3.0 | PMOS, pre-charges M4 gate |
| M4C (startup) | 1.0 | NMOS, startup assist |
| M5 (VGATE pull-down) | 1.0 | NMOS, gate discharge |
| M5A (cascode) | 1.0 | NMOS, protects M5 from Vds overvoltage |
| Inverter | 3.0/1.0 | PMOS/NMOS, generates CLKSB |

Edit the `W` dict in `bootstrap_common.py` to change sizes.

## Bootstrap Capacitor

Default CB = 1 pF. Larger CB → less voltage droop (VGATE closer to VIN+VDD).
Rule of thumb: CB should be ≥5× the gate capacitance Cgg of MS.

## Output & File Conventions

- **All generated files** go to `WORK/` — never inside the skill package.
- **Never pop-up figures** — save PNGs via `fig.savefig()` + `plt.close()`.
- **Comparison plots: max 3 vertically stacked subplots.**

## Key Metrics

1. **Bootstrap voltage**: VGATE − VIN ≈ VDD (ideally 1.8V, typically 1.6–1.75V due to parasitic capacitance)
2. **On-resistance**: Ron of MS during sampling phase (target: <50 Ω for typical SAR ADC)
3. **Ron flatness**: Ron variation across VIN = 0 to VDD (bootstrap switch should be nearly flat vs. NMOS/CMOS curves)
