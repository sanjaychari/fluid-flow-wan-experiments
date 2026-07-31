#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "configs"
CFG.mkdir(parents=True, exist_ok=True)


def config_text(*, topology: str, workload: str, seed: int, send: int, drain: int,
                generation_every: int | None = None, flow_min: int | None = None,
                flow_max: int | None = None, trace: str | None = None,
                pause_hi: float = 0.80, pause_lo: float = 0.50) -> str:
    workload_lines = ""
    if workload == "random":
        workload_lines = f'''    rng_seed: {seed}\n    flow_generation_every_n_intervals: {generation_every}\n    random_flow_min: "{flow_min} Gb"\n    random_flow_max: "{flow_max} Gb"\n'''
    else:
        workload_lines = '    traffic_trace_file: "traffic.csv"\n'
    return f'''schema_version: 1

topology:
  format: groups
  params:
    message_size: 32768
    pe_mem_factor: 1024
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        fluid-flow-wan-switch-lp: 64
        fluid-flow-wan-terminal-lp: 128

sections:
  fluid_flow_wan:
    topology_yaml_file: "topology.yaml"
{workload_lines}    interval_seconds: 10
    num_send_intervals: {send}
    num_drain_intervals: {drain}
    egress_model: pdes
    debug_prints: 0
    backpressure_delay_ms: 1.0
    pause_high_watermark_fraction: {pause_hi:.2f}
    pause_low_watermark_fraction: {pause_lo:.2f}
    terminal_log_path: "logs/terminal-events.csv"
    switch_log_path: "logs/switch-events.csv"
    fluid_segment_log_path: "logs/fluid-segment-events.csv"
'''


cases = []
# Ten paired stochastic seeds are shared across the load, buffer/PAUSE,
# and incast treatments.
seeds = tuple(range(2001, 2011))
loads = {
    "low": (8, 200, 400),
    "medium": (4, 300, 600),
    "high": (2, 400, 800),
}

# A: load transition on the fixed 100 Gb topology and moderate PAUSE.
for level, (period, lo, hi) in loads.items():
    for seed in seeds:
        name = f"load-{level}-seed{seed}"
        path = CFG / f"{name}.yaml"
        path.write_text(config_text(topology="topologies/topology-buffer100Gb.yaml", workload="random", seed=seed,
                                    send=20, drain=20, generation_every=period, flow_min=lo, flow_max=hi))
        cases.append((name, "A-load", seed, "random", path.relative_to(ROOT),
                      "topologies/topology-buffer100Gb.yaml", ""))

# B: buffer/PAUSE Pareto under high load.
policies = {"aggressive": (0.50, 0.30), "moderate": (0.80, 0.50)}
for buffer_gb in (25, 100, 400):
    for policy, (phi, plo) in policies.items():
        for seed in seeds:
            name = f"buffer{buffer_gb}Gb-{policy}-seed{seed}"
            path = CFG / f"{name}.yaml"
            period, lo, hi = loads["high"]
            path.write_text(config_text(topology=f"topologies/topology-buffer{buffer_gb}Gb.yaml", workload="random",
                                        seed=seed, send=20, drain=20, generation_every=period,
                                        flow_min=lo, flow_max=hi, pause_hi=phi, pause_lo=plo))
            cases.append((name, "B-buffer-pause", seed, "random", path.relative_to(ROOT),
                          f"topologies/topology-buffer{buffer_gb}Gb.yaml", ""))

# C: 4/8/16-source incast, paired source-set seeds.
for fanin in (4, 8, 16):
    for seed in seeds:
        name = f"incast-{fanin}-seed{seed}"
        path = CFG / f"{name}.yaml"
        path.write_text(config_text(topology="topologies/topology-buffer100Gb.yaml", workload="trace", seed=seed,
                                    send=20, drain=20, trace=f"traces/{name}.csv"))
        cases.append((name, "C-incast", seed, "trace", path.relative_to(ROOT),
                      "topologies/topology-buffer100Gb.yaml", f"traces/{name}.csv"))

# D: deterministic elephant/victim trace, asymmetric vs bandwidth-symmetric reverse edge.
for mode in ("asymmetric", "symmetric"):
    name = f"victim-{mode}"
    path = CFG / f"{name}.yaml"
    path.write_text(config_text(topology=f"topologies/topology-victim-{mode}.yaml", workload="trace", seed=0,
                                send=40, drain=20, trace=f"traces/{name}.csv"))
    cases.append((name, "D-victim", 0, "trace", path.relative_to(ROOT),
                  f"topologies/topology-victim-{mode}.yaml", f"traces/{name}.csv"))

with (ROOT / "cases.csv").open("w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "scenario", "seed", "workload", "config", "topology", "trace"])
    w.writerows(cases)
print(f"wrote {len(cases)} Experiment 2 cases")
