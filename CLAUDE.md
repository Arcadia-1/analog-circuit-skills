# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Analog circuit simulation framework: ngspice + Python for StrongArm dynamic comparator analysis (45nm PTM HP, VDD=1.0V, CLK=1GHz).

**Dependencies**: ngspice (on PATH), Python 3 with numpy, matplotlib, scipy.

## Running Simulations

```bash
cd comparator/assets
python run_tran_strongarm_comp.py      # Master: all 3 sims in parallel (~13s)
python run_tran_strongarm_wave.py      # Waveform only
python run_tran_strongarm_noise.py     # Noise extraction + FOM
python run_tran_strongarm_ramp.py      # Ramp response only
```

All outputs go to `.work_comparator/` at repo root (logs → `.work_comparator/logs/`, plots → `.work_comparator/plots/`). Override with `ANALOG_WORK_DIR` env var.

## Architecture

### Execution flow

```
run_*.py (entry points)
  → simulate_*.py (render netlist, call ngspice, parse output)
  → plot_*.py (generate PNG figures)

Shared infrastructure:
  ngspice_common.py    — paths, ngspice runner, wrdata parser, template renderer
  comparator_common.py — circuit params, DUT rendering, signal processing (sample_output, sigma_from_p1, fit_transfer_curve)
```

### Template-based netlist generation

SPICE netlists are generated from `.cir.tmpl` files in `comparator/assets/netlist/` using Python `str.format()`. The DUT subcircuit is rendered separately via `render_dut()` and included via `.include`.

Key templates:
- `comparator_strongarm.cir.tmpl` — DUT subcircuit (parameterized W, L)
- `testbench_cmp_tran.cir.tmpl` — waveform capture (few cycles, no noise)
- `testbench_cmp_tran_noise.cir.tmpl` — statistics (1000 cycles, trnoise injected)
- `testbench_cmp_ramp.cir.tmpl` — ramp input (100 cycles)

### Data flow

ngspice `wrdata` → 2-column text files (time, value) → `parse_wrdata()` → numpy arrays → analysis/plotting.

## Key Conventions

- **Skill-specific output directories**: comparator → `.work_comparator/`, bootstrap_switch → `.work_bootstrap/`. Never write inside the skill package.
- **Matplotlib `Agg` backend always** — never pop up figures. Always `plt.close(fig)` after `savefig()`.
- **Forward slashes in paths** for ngspice compatibility (`spath()` helper).
- **Parallel execution** via `ThreadPoolExecutor` for independent simulations.
- **Comparison plots: max 3 vertically stacked subplots** with related signals grouped.
- **Editable circuit parameters** (transistor widths, noise config) are globals in `comparator_common.py` and `simulate_tran_strongarm_comp.py`.

## Noise Extraction Method

Single-point probit: inject trnoise at INP/INN, run 1000 cycles at fixed Vin, count P(HIGH), compute σ = Vin / Φ⁻¹(P1). FOM1 = E_cycle × σ², FOM2 = FOM1 × Tcmp.
