#!/usr/bin/env python3
"""Run two-stage op amp noise simulation."""

from ngspice_common import check_ngspice
from plot_opamp import plot_noise
from simulate_opamp_noise import simulate_noise


def main():
    check_ngspice()
    result = simulate_noise()
    plot_noise(result)
    return result


if __name__ == "__main__":
    main()
