#!/usr/bin/env python3
"""run_ldo_noise.py -- Standalone noise simulation entry point."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from simulate_ldo_noise import simulate_noise
from plot_ldo_noise import plot_noise

if __name__ == "__main__":
    results = simulate_noise()
    plot_noise(results)
