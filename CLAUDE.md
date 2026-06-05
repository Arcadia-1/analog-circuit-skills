# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Analog circuit simulation framework: ngspice + Python for block-level analog circuits, including StrongArm dynamic comparator analysis, bootstrap switches, LDO experiments, a five-transistor CMOS OTA, and a Miller-compensated two-stage op amp.

**Dependencies**: ngspice (on PATH), Python 3 with numpy, matplotlib, scipy.

## Running Simulations

```bash
cd comparator/assets
python run_tran_strongarm_comp.py      # Master: all 3 sims in parallel (~13s)
python run_tran_strongarm_wave.py      # Waveform only
python run_tran_strongarm_noise.py     # Noise extraction + FOM
python run_tran_strongarm_ramp.py      # Ramp response only

python five_transistor_ota/scripts/run_ota.py  # Five-transistor OTA: DC, AC, noise
python two_stage_opamp/scripts/run_opamp.py    # Two-stage op amp: DC operating point, AC gain/phase, PZ, noise
```

Comparator outputs go to `.work_comparator/` at repo root (logs → `.work_comparator/logs/`, plots → `.work_comparator/plots/`). LDO, five-transistor OTA, and two-stage op amp outputs go to `WORK/` by default. Override with `ANALOG_WORK_DIR` env var.

## Architecture

### Execution flow

```
run_*.py (entry points)
  → simulate_*.py (render netlist, call ngspice, parse output)
  → plot_*.py (generate PNG figures)

Shared infrastructure:
  ngspice_common.py    — paths, ngspice runner, wrdata parser, template renderer
  *_common.py         — circuit params, DUT rendering, signal processing helpers
```

### Template-based netlist generation

SPICE netlists are generated from `.cir.tmpl` files in `comparator/assets/netlist/` using Python `str.format()`. The DUT subcircuit is rendered separately via `render_dut()` and included via `.include`.

Comparator templates:
- `comparator_strongarm.cir.tmpl` — DUT subcircuit (parameterized W, L)
- `testbench_cmp_tran.cir.tmpl` — waveform capture (few cycles, no noise)
- `testbench_cmp_tran_noise.cir.tmpl` — statistics (1000 cycles, trnoise injected)
- `testbench_cmp_ramp.cir.tmpl` — ramp input (100 cycles)

Five-transistor OTA templates live under `five_transistor_ota/assets/netlist/` and cover DUT, DC transfer, AC open-loop response, and output noise.
Two-stage op amp templates live under `two_stage_opamp/assets/netlist/` and cover DUT, DC operating point, AC gain/phase sweep, pole-zero analysis, and output noise.

### Data flow

ngspice `wrdata` → 2-column text files (time, value) → `parse_wrdata()` → numpy arrays → analysis/plotting.

## Key Conventions

- **Skill-specific output directories**: comparator → `.work_comparator/`, bootstrap_switch → `.work_bootstrap/`, LDO / five_transistor_ota / two_stage_opamp → `WORK/`. Never write inside the skill package.
- **Matplotlib `Agg` backend always** — never pop up figures. Always `plt.close(fig)` after `savefig()`.
- **Forward slashes in paths** for ngspice compatibility (`spath()` helper).
- **Parallel execution** via `ThreadPoolExecutor` for independent simulations.
- **Comparison plots: max 3 vertically stacked subplots** with related signals grouped.
- **Editable circuit parameters** (transistor widths, noise config) are globals in `comparator_common.py` and `simulate_tran_strongarm_comp.py`.

## Noise Extraction Method

Single-point probit: inject trnoise at INP/INN, run 1000 cycles at fixed Vin, count P(HIGH), compute σ = Vin / Φ⁻¹(P1). FOM1 = E_cycle × σ², FOM2 = FOM1 × Tcmp.
