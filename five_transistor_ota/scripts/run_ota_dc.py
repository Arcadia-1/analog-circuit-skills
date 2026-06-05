#!/usr/bin/env python3
from simulate_ota_dc import simulate_dc
from plot_ota import plot_dc

if __name__ == "__main__":
    plot_dc(simulate_dc())

