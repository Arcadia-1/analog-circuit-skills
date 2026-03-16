#!/usr/bin/env python3
"""Entry point: bootstrap switch waveform simulation + plot."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bootstrap_common import check_ngspice
from simulate_tran_bts_wave import simulate_wave
from plot_tran_bts_wave import plot_wave

if __name__ == "__main__":
    check_ngspice()
    results = simulate_wave()
    plot_wave(results)
    print("\nDone.")
