---
name: comparator
description: "StrongArm dynamic comparator simulation and analysis skill. Use when the user wants to: (1) simulate a StrongArm comparator with ngspice, (2) run transient noise simulation and count output statistics (0/1) over many cycles, (3) plot transition waveforms showing internal nodes (VXP/VXN, VLP/VLN, OUTP/OUTN), (4) simulate ramp input and observe the noise-induced transition region, (5) learn the StrongArm comparator topology, working phases, noise model, or performance metrics (Tcmp, power, FOM). Requires: ngspice installed, Python 3 with numpy/matplotlib/scipy."
---

# StrongArm Comparator Skill

**Dependencies**: `ngspice`, Python 3 + `numpy`, `matplotlib`, `scipy`.

## Asset Layout

```
assets/
├── ngspice_common.py               — shared utilities: paths, runner, parser, template renderer
├── models/
│   └── ptm45hp.lib                 — PTM 45nm HP BSIM4 model (VDD=1.0V)
├── netlist/
│   ├── comparator_strongarm.cir.tmpl  — DUT: .subckt comparator_strongarm (parameterized L, W)
│   ├── testbench_cmp_tran.cir.tmpl    — TB: 5-cycle waveform (all internal nodes + VDD current)
│   ├── testbench_cmp_tran_noise.cir.tmpl — TB: 1000-cycle statistics (noise counting)
│   └── testbench_cmp_ramp.cir.tmpl    — TB: 100-cycle ramp input (−1mV → +1mV)
├── simulate_tran_strongarm_comp.py — simulation engine (5 parallel runs) + compute_fom()
├── plot_tran_strongarm_comp.py     — plotting (waveform + statistics figures)
├── run_tran_strongarm_comp.py      — entry point
├── logs/                           — ngspice logs + fom_report.txt (auto-created)
└── plots/                          — output PNGs (auto-created)
```

## Running

```bash
cd comparator/assets
python run_tran_strongarm_comp.py
```

Runs 5 simulations in parallel (~13s on a modern PC):
1. **Waveform** — Vin=+1mV, 5 cycles, all internal nodes
2. **Stat Vin=+1mV** — 1000 cycles → count HIGH/LOW
3. **Stat Vin=0mV** — 1000 cycles → count HIGH/LOW
4. **Stat Vin=−1mV** — 1000 cycles → count HIGH/LOW
5. **Ramp** — Vin ramps −1mV→+1mV, 100 cycles

Outputs: `plots/strongarm_waveform.png`, `plots/strongarm_stats.png`.

## Circuit Topology

StrongArm comparator, 45nm PTM HP, VDD=1.0V, CLK=1GHz, VCM=0.5V.

```
Transistor  Type   Gate  Drain  Source  Role
──────────────────────────────────────────────────────────
M0          NMOS   CLK   VS     GND     Tail (evaluation switch)
M1          NMOS   INP   VXP    VS      Input pair (+)
M2          NMOS   INN   VXN    VS      Input pair (−)
M3          NMOS   VLN   VLP    VXP     NMOS latch (stacked on M1)
M4          NMOS   VLP   VLN    VXN     NMOS latch (stacked on M2)
M5          PMOS   VLN   VLP    VDD     PMOS latch (cross-coupled)
M6          PMOS   VLP   VLN    VDD     PMOS latch (cross-coupled)
M7–M10      PMOS   CLK   VX/VL  VDD     Reset (pull to VDD when CLK=0)
M11–M14     CMOS   VLP/VLN  OUTP/OUTN  Output inverters
```

**Critical connection:** M3 source = VXP (NOT GND). As VXP drops during integration,
`Vgs_M3 = VLN − VXP` increases → M3 turns on when VXP < VDD − Vth.
Current path: GND → M0 → M1 → VXP → M3 → VLP.

**Output polarity:** OUTP = NOT(VLP) = 1 when INP > INN.

## Noise Model

Transient noise is modeled as two independent `trnoise` voltage sources at INP/INN:
- Noise amplitude per side: `na = σ_diff / √2`  (default σ_diff = 600 µV)
- Noise bandwidth: 10 GHz → `nt = 1/(2×10GHz) = 50 ps`
- Differential noise std: `σ_diff = √2 × na`

To change noise level or bandwidth, edit `simulate_tran_strongarm_comp.py`:
```python
SIGMA_DIFF = 600e-6   # V  input-referred differential RMS noise
NOISE_BW   = 10e9     # Hz noise bandwidth
```

## Transistor Sizes (all L = 45 nm)

| Device | W (µm) | Description |
|--------|--------|-------------|
| Tail M0 | 4.0 | Controls evaluation current |
| Input M1/M2 | 4.0 | Wider → lower noise |
| NMOS latch M3/M4 | 1.0 | Latch speed |
| PMOS latch M5/M6 | 2.0 | Regeneration time constant τ |
| Reset M7–M10 | 1.0 | Reset speed |
| Output inv | 2.0 / 1.0 | PMOS / NMOS |

Edit the `W = dict(...)` in `simulate_tran_strongarm_comp.py` to sweep sizes.

## References

- **Circuit theory & working phases**: See `references/comparator_theory.md`
- **Noise simulation methods (time-domain + PSS/PNoise)**: See `references/noise_sim.md`
- **Speed, power, and FOM measurement**: See `references/speed_sim.md`
