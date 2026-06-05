#!/usr/bin/env python3
from simulate_ota_noise import simulate_noise
from plot_ota import plot_noise

if __name__ == "__main__":
    plot_noise(simulate_noise())

