#!/usr/bin/env python3
"""Run two-stage op amp AC gain/phase simulation."""

from ngspice_common import check_ngspice
from plot_opamp import plot_ac
from simulate_opamp_ac import simulate_ac


def main():
    check_ngspice()
    result = simulate_ac()
    plot_ac(result)
    return result


if __name__ == "__main__":
    main()
