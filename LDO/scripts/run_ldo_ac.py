#!/usr/bin/env python3
"""
run_ldo_ac.py
=============
Entry point: LDO AC simulations (PSRR, Zout, loop gain / phase margin).

Usage
-----
  cd LDO/scripts/
  python run_ldo_ac.py

Output
------
  WORK/plots/ldo_ac.png
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_ldo_ac import simulate_ac
from plot_ldo_ac import plot_ac


def main():
    results = simulate_ac()
    plot_ac(results)
    print("\nDone.")


if __name__ == "__main__":
    main()
