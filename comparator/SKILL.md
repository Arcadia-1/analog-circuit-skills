---
name: comparator
description: "StrongArm dynamic comparator simulation and analysis skill. Use this skill whenever the user wants to simulate, analyse, or learn about a StrongArm (or similar dynamic) comparator. Trigger on any of: (1) run a comparator transient simulation in ngspice, (2) plot waveforms of internal nodes (VXP/VXN, VLP/VLN, OUTP/OUTN), (3) measure or sweep comparison time Tcmp, latch time constant τ, average power, energy per cycle, or FOM, (4) extract input-referred noise sigma via noise counting / probit / Gaussian CDF fit, (5) sweep transistor widths (tail, input pair, latch NMOS/PMOS) to study speed–power–noise trade-offs, (6) simulate offset voltage with ramp or binary-search method, (7) learn the StrongArm topology, four operating phases, noise/offset/speed theory, or transistor sizing guidance. Requires: ngspice on PATH, Python 3 + numpy/matplotlib/scipy."
---

# StrongArm Comparator Skill

**Dependencies**: `ngspice` on PATH, Python 3 + `numpy`, `matplotlib`, `scipy`.

## Layout

```
comparator/
├── SKILL.md
├── scripts/                        ← run from here (cd comparator/scripts)
│   ├── ngspice_common.py           — paths, ngspice runner, parser, template renderer
│   ├── comparator_common.py        — circuit params, DUT rendering, τ/Tcmp/noise helpers
│   │
│   ├── simulate_tran_strongarm_wave.py   — backend: 3-cycle waveform + τ extraction
│   ├── simulate_tran_strongarm_noise.py  — backend: noise (probit) + power + Tcmp
│   ├── simulate_tran_strongarm_ramp.py   — backend: ramp transfer curve
│   ├── plot_tran_strongarm_wave.py       — plot: all internal nodes
│   ├── plot_tran_strongarm_noise.py      — plot: CDF fit + statistics
│   ├── plot_tran_strongarm_ramp.py       — plot: transfer curve
│   │
│   ├── run_tran_strongarm_comp.py   ← MAIN entry point (wave + noise + ramp in parallel)
│   ├── run_tran_strongarm_wave.py   — standalone: waveform only
│   ├── run_tran_strongarm_noise.py  — standalone: noise + FOM only
│   ├── run_tran_strongarm_ramp.py   — standalone: ramp only
│   │
│   ├── run_tcmp_sweep_plot.py       — sweep W_tail/inp/lat_n/lat_p → Tcmp plots
│   ├── run_tau_sweep_plot.py        — sweep W_lat_n/lat_p/inp → τ plots
│   ├── run_power_sweep_plot.py      — sweep W_tail/inp/lat_n/lat_p → power plots
│   │
│   ├── run_sweep_input_amplitude.py — Vin_diff → Tcmp curve
│   ├── run_sweep_vcm.py             — VCM → σ_n
│   ├── run_sweep_noise_bw.py        — noise BW → σ_n
│   ├── run_sweep_k_valid.py         — σ_n vs input amplitude (validation)
│   ├── run_compare_wave.py          — StrongArm vs Miyahara waveform comparison
│   └── diag_high_vcm.py            — diagnostic: behaviour at high VCM
│
├── assets/
│   ├── netlist/                    ← SPICE templates (*.cir.tmpl)
│   └── models/ptm45hp.lib          ← PTM 45nm HP BSIM4 model
│
└── references/                     ← read when user asks about theory/noise/offset
    ├── 01_theory.md
    ├── 02_speed.md
    ├── 03_noise.md
    └── 04_offset.md
```

All generated files (logs, plots, netlists) go to `WORK/` at the repo root — never inside the skill package. Override with env-var `ANALOG_WORK_DIR`.

## Task → Script Decision Guide

| User asks about | Script to run |
|-----------------|---------------|
| Full characterisation (waveform + noise + ramp) | `run_tran_strongarm_comp.py` |
| Waveform / internal nodes only | `run_tran_strongarm_wave.py` |
| Noise sigma / FOM only | `run_tran_strongarm_noise.py` |
| Ramp transfer curve only | `run_tran_strongarm_ramp.py` |
| Tcmp vs transistor width | `run_tcmp_sweep_plot.py` |
| τ vs transistor width | `run_tau_sweep_plot.py` |
| Power vs transistor width | `run_power_sweep_plot.py` |
| Tcmp vs input amplitude | `run_sweep_input_amplitude.py` |
| Noise vs VCM | `run_sweep_vcm.py` |
| Noise vs noise bandwidth | `run_sweep_noise_bw.py` |
| StrongArm vs Miyahara comparison | `run_compare_wave.py` |
| Theory / operating phases | Read `references/01_theory.md` |
| Speed / Tcmp / τ theory | Read `references/02_speed.md` |
| Noise theory / FOM | Read `references/03_noise.md` |
| Offset voltage | Read `references/04_offset.md` |

## Running

```bash
cd comparator/scripts
python run_tran_strongarm_comp.py
```

Runs 3 simulations in parallel (~10s on a modern PC):
1. **Waveform** — Vin=+1mV, 3 cycles, all internal nodes → τ extracted
2. **Noise** — 1000 cycles with trnoise → P(1) → σ_n via probit; also measures power and Tcmp
3. **Ramp** — Vin ramps −2mV→+2mV, 100 cycles → transfer curve

Key outputs in `WORK/`:
- `plots/strongarm_waveform.png`
- `plots/strongarm_noise.png`
- `plots/strongarm_ramp.png`
- `logs/fom_report.txt` — σ_n, P_avg, Tcmp, FOM1, FOM2

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

## Transistor Sizes (all L = 45 nm)

Defined in `comparator_common.py` → `W = dict(...)`:

| Device | W (µm) | Design note |
|--------|--------|-------------|
| Tail M0 | 4.0 | ↑W → faster integration; diminishing returns beyond 4µm |
| Input M1/M2 | 4.0 | ↑W → lower noise, faster integration, but more VX cap |
| NMOS latch M3/M4 | 1.0 | ↑W adds drain cap; τ nearly flat (gm and C cancel) |
| PMOS latch M5/M6 | 2.0 | ↑W → shorter τ up to ~4µm, then saturates |
| Reset M7–M10 | 1.0 | Reset speed; rarely a bottleneck |
| Output inv PMOS | 2.0 | Output drive strength |
| Output inv NMOS | 1.0 | Output drive strength |

## Noise Model

Two independent `trnoise` sources at INP/INN (band-limited white noise):

```python
# comparator_common.py
NOISE_BW = 100e9        # Hz  (100 GHz — decorrelates between 1 GHz cycles)
NOISE_NT = 1/(2*NOISE_BW)  # 5 ps  update interval
NOISE_NA = 300e-6       # V   amplitude per side
```

Noise is a stimulus parameter only; true σ_n is extracted from P(1) statistics via the probit method: `σ_n = Vin_fixed / norm.ppf(P1)` with Vin_fixed = 0.35 mV.

## Output & File Conventions

- **Never open/pop-up figures** — only save PNGs via `fig.savefig()` + `plt.close()`.
- **Netlists** → `WORK/netlists/dut/` (DUT) and `WORK/netlists/testbench/` (testbenches).
- **Comparison plots: max 3 vertically stacked subplots.** Group related signals:
  1. CLK + INP/INN
  2. Latch nodes VLP/VLN
  3. Output OUTP/OUTN

## References

| File | Topic |
|------|-------|
| `references/01_theory.md` | Topology, 4-phase operation, latch regeneration |
| `references/02_speed.md` | Tcmp definition, τ extraction, speed vs sizing |
| `references/03_noise.md` | Error probability, probit method, FOM1/FOM2 |
| `references/04_offset.md` | Offset vs noise, ramp & binary-search methods |
