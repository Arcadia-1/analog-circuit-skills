#!/usr/bin/env python3
"""
run_tran_bts_ron.py
===================
Entry point: Ron comparison at all three technology nodes (180nm / 45nm / 22nm).
Runs simulations in parallel, generates single-node + three-panel plots.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concurrent.futures import ThreadPoolExecutor
from bootstrap_common import check_ngspice
from simulate_tran_bts_ron import simulate_ron, NODE_CONFIGS
from plot_tran_bts_ron import plot_ron, plot_ron_multinode

if __name__ == "__main__":
    check_ngspice()

    print("\n=== Bootstrap Switch — Ron Comparison (180nm / 45nm / 22nm) ===")
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=len(NODE_CONFIGS)) as pool:
        futures = [pool.submit(simulate_ron, cfg) for cfg in NODE_CONFIGS]
        node_results = [f.result() for f in futures]

    # Single-node plot (180nm, for standalone use)
    plot_ron(node_results[0])

    # Three-panel comparison
    plot_ron_multinode(node_results)

    print(f"\n  Total wall time: {time.perf_counter() - t0:.1f}s")
    print("  Done.")
