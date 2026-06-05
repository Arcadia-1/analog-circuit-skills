---
name: five_transistor_ota
description: "Five-transistor OTA simulation and analysis skill. Use when the user wants to simulate or size a classic 5T CMOS OTA: NMOS differential input pair, PMOS current-mirror active load, and NMOS tail current transistor. Supports ngspice DC transfer, AC gain/bandwidth/phase, output-noise analysis, and first-order design interpretation. Requires ngspice on PATH and Python 3 with numpy/matplotlib/scipy."
---

# Five-Transistor OTA Skill

Classic single-ended 5T CMOS OTA using PTM 180nm models.

## Topology

```
             VDD
              |
       M3 PMOS mirror output      M4 PMOS diode load
              |                         |
             OUT                       NETD
              |                         |
       M0 NMOS input +           M1 NMOS input -
              \_______________________/
                         |
                        TAIL
                         |
                M5 NMOS tail source
                         |
                        VSS
```

Ports: `INP`, `INN`, `OUT`, `VDD`, `VSS`, `VBIAS`.

## Running

```bash
cd five_transistor_ota/scripts
python run_ota.py
```

This runs:

- DC transfer curve around the input common-mode point.
- AC open-loop gain from differential input to output.
- Output-referred noise density and integrated RMS noise.

Outputs go to `WORK/plots`, `WORK/logs`, and `WORK/netlists`.

## Main Scripts

| Task | Script |
|------|--------|
| Full simulation | `run_ota.py` |
| DC only | `run_ota_dc.py` |
| AC only | `run_ota_ac.py` |
| Noise only | `run_ota_noise.py` |

## Design Knobs

Edit `scripts/ota_common.py`:

- `W_IN_UM`, `L_IN_NM`, `M_IN` — input pair sizing.
- `W_LOAD_UM`, `L_LOAD_NM`, `M_LOAD` — PMOS mirror load sizing.
- `W_TAIL_UM`, `L_TAIL_NM`, `M_TAIL` — tail transistor sizing.
- `VBIAS` — tail gate bias.
- `C_LOAD` and `R_LOAD` — output loading.
