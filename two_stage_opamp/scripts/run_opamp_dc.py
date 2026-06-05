#!/usr/bin/env python3
"""Run two-stage op amp DC operating-point simulation."""

from ngspice_common import check_ngspice
from plot_opamp import plot_dc_nodes
from simulate_opamp_dc import simulate_dc


def main():
    check_ngspice()
    result = simulate_dc()
    plot_dc_nodes(result)
    return result


if __name__ == "__main__":
    main()
