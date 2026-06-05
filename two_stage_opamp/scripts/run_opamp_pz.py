#!/usr/bin/env python3
"""Run two-stage op amp pole-zero simulation."""

from ngspice_common import check_ngspice
from simulate_opamp_pz import simulate_pz


def main():
    check_ngspice()
    return simulate_pz()


if __name__ == "__main__":
    main()
