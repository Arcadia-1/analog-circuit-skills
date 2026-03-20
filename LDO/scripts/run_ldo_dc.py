#!/usr/bin/env python3
"""
run_ldo_dc.py
=============
Entry point: LDO DC simulations (operating point, line reg, load reg).

Usage
-----
  cd LDO/scripts/
  python run_ldo_dc.py

Output
------
  WORK/plots/ldo_dc.png
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_ldo_dc import simulate_dc
from plot_ldo_dc import plot_dc


def main():
    results = simulate_dc()
    plot_dc(results)
    print("\nDone.")


if __name__ == "__main__":
    main()
