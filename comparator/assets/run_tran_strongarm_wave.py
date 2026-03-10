#!/usr/bin/env python3
"""
run_tran_strongarm_wave.py
==========================
Standalone entry point: 3-cycle waveform simulation, Vin=+1mV.

Usage
-----
  cd comparator/assets/
  python run_tran_strongarm_wave.py

Output
------
  plots/strongarm_waveform.png
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_tran_strongarm_wave import simulate_wave
from plot_tran_strongarm_wave import plot_wave


def main():
    results = simulate_wave()
    plot_wave(results["wave"], results["params"])
    print("\nDone.")


if __name__ == "__main__":
    main()
