#!/usr/bin/env python3
from simulate_ota_ac import simulate_ac
from plot_ota import plot_ac

if __name__ == "__main__":
    plot_ac(simulate_ac())

