---
name: comparator
description: "StrongArm dynamic comparator simulation and analysis skill. Use when the user wants to: (1) simulate a StrongArm comparator with ngspice, (2) run transient noise simulation and count output statistics (0/1) over many cycles, (3) plot transition waveforms showing internal nodes (VXP/VXN, VLP/VLN, OUTP/OUTN), (4) simulate ramp input and observe the noise-induced transition region, (5) measure comparison time Tcmp, average power, energy per cycle, or FOM, (6) extract input-referred noise sigma via probit / Gaussian CDF fit, (7) measure or simulate offset voltage using binary-search method, (8) learn the StrongArm topology, four operating phases (Reset/Integration/NMOS Latch/CMOS Latch), noise theory, or transistor sizing trade-offs. Requires: ngspice installed, Python 3 with numpy/matplotlib/scipy."
---

# StrongArm Comparator Skill

**Dependencies**: `ngspice`, Python 3 + `numpy`, `matplotlib`, `scipy`.

## Asset Layout

```
assets/
├── comparator_common.py            — circuit parameters, DUT rendering, signal-processing helpers
├── ngspice_common.py               — shared utilities: paths, runner, parser, template renderer
├── models/
│   └── ptm45hp.lib                 — PTM 45nm HP BSIM4 model (VDD=1.0V)
├── netlist/
│   ├── comparator_strongarm.cir.tmpl     — DUT: .subckt comparator_strongarm (parameterised L, W)
│   ├── testbench_cmp_tran.cir.tmpl       — TB: 3-cycle waveform (all internal nodes)
│   ├── testbench_cmp_tran_noise.cir.tmpl — TB: N-cycle statistics with trnoise
│   └── testbench_cmp_ramp.cir.tmpl       — TB: 100-cycle ramp input (−2mV → +2mV)
├── simulate_tran_strongarm_wave.py — simulation backend: 3-cycle waveform + τ extraction
├── simulate_tran_strongarm_noise.py — simulation backend: noise (probit) + power + Tcmp
├── simulate_tran_strongarm_ramp.py — simulation backend: ramp transfer curve
├── plot_tran_strongarm_wave.py     — plot: waveform (all internal nodes)
├── plot_tran_strongarm_noise.py    — plot: noise CDF fit + statistics
├── plot_tran_strongarm_ramp.py     — plot: ramp transfer curve
├── run_tran_strongarm_comp.py      — entry point (runs all three in parallel)
├── run_tran_strongarm_wave.py      — standalone: waveform only
├── run_tran_strongarm_noise.py     — standalone: noise + FOM only
├── run_tran_strongarm_ramp.py      — standalone: ramp only
├── run_tcmp_sweep_plot.py          — sweep W_tail/inp/lat_n/lat_p → Tcmp plots
├── run_tau_sweep_plot.py           — sweep W_lat_n/lat_p/inp → τ plots
├── run_power_sweep_plot.py         — sweep W_tail/inp/lat_n/lat_p → power plots
└── run_sweep_*/simulate_sweep_*/plot_sweep_*  — analysis sweeps (VCM, noise BW, input amplitude)
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

To change noise level or bandwidth, edit `comparator_common.py`:
```python
NOISE_NA = 300e-6    # V  noise amplitude per side
NOISE_BW = 100e9     # Hz noise bandwidth
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

Edit the `W = dict(...)` in `comparator_common.py` to change transistor sizes.

## Output & File Conventions

- **All generated files** (logs, plots, data) go to `H:\analog-circuit-skills\WORK\` — never
  inside the skill package itself.
  - Logs  → `WORK/logs/`
  - Plots → `WORK/plots/`
  - Override with env-var `ANALOG_WORK_DIR`.
- **Never open/pop-up figures** — only save PNGs via `fig.savefig()` + `plt.close()`.
- **Comparison plots: max 3 vertically stacked subplots.**
  When comparing two topologies, group related signals together rather than giving
  each signal its own row.  Suggested grouping for a 3-row comparison:
  1. CLK + INP/INN  (shared stimulus)
  2. Latch nodes VLP / VLN  (both topologies overlaid)
  3. Output OUTP / OUTN     (both topologies overlaid)

## References

Four detailed reference files cover the full tutorial content:

| File | Topic | Key content |
|------|-------|-------------|
| `references/01_theory.md` | Circuit theory & operating phases | StrongArm topology (14 transistors), 4-phase operation (Reset/Integration/NMOS Latch/CMOS Latch), latch regeneration $v_d = v_{d0}e^{t/\tau}$, simulation checkpoints |
| `references/02_speed.md` | Tcmp and energy measurement | Tcmp definition, CROSS expression, energy expression, Tcmp vs Vin table (307→78 ps for 100µV→1V), τ extraction, ngspice Python equivalent |
| `references/03_noise.md` | Input-referred noise | Error probability $P_{error}=\Phi(-V_{in}/\sigma)$, probit extraction, time-domain statistical method, PSS/PNoise setup (Cadence), transistor sizing vs noise, FOM1/FOM2 |
| `references/04_offset.md` | Offset voltage | Offset vs noise distinction, ramp & binary-search methods, Verilog-A `_va_offset` module, mismatch cap injection (−5.5 mV/fF), Monte Carlo ($\sigma_{os}=3.45$ mV at W=10µm), Pelgrom scaling |

Read the relevant file when the user asks about theory, simulation setup, noise, or offset.
