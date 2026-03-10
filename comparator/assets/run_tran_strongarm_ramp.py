#!/usr/bin/env python3
"""
run_tran_strongarm_ramp.py
==========================
Standalone entry point: 100-cycle ramp simulation (-2mV to +2mV).

Usage
-----
  cd comparator/assets/
  python run_tran_strongarm_ramp.py

Output
------
  plots/strongarm_ramp.png
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_tran_strongarm_ramp import simulate_ramp
from plot_tran_strongarm_ramp import plot_ramp


def main():
    results = simulate_ramp()
    plot_ramp(results["ramp"], results["params"])
    print("\nDone.")


if __name__ == "__main__":
    main()
