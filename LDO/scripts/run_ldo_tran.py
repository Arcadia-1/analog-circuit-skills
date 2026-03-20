#!/usr/bin/env python3
"""
run_ldo_tran.py
===============
Entry point: load-step transient simulation only.

Usage
-----
  cd LDO/scripts/
  python run_ldo_tran.py

Output
------
  WORK/plots/ldo_tran.png
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulate_ldo_tran import simulate_tran
from plot_ldo_tran      import plot_tran


def main():
    results = simulate_tran()
    plot_tran(results)


if __name__ == "__main__":
    main()
