#!/usr/bin/env python3
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "configs"
CFG.mkdir(parents=True, exist_ok=True)

loads = {
    "medium": (4, 300, 600),
    # Preserve the established stress point that generated the large query counts.
    "high": (4, 1000, 4000),
}
seed = 3001
cases = []
pairs = []
for switches in (32, 64, 128):
    terminals = switches * 2
    selected = ("high",) if switches == 128 else ("medium", "high")
    for load in selected:
        period, lo, hi = loads[load]
        pair = {}
        for mode in ("pdes", "statistical"):
            name = f"scale{switches}-{load}-{mode}"
            path = CFG / f"{name}.yaml"
            path.write_text(f'''schema_version: 1

topology:
  format: groups
  params:
    message_size: 32768
    pe_mem_factor: 1024
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        fluid-flow-wan-switch-lp: {switches}
        fluid-flow-wan-terminal-lp: {terminals}

sections:
  fluid_flow_wan:
    topology_yaml_file: "topology.yaml"
    interval_seconds: 10
    num_send_intervals: 40
    num_drain_intervals: 20
    rng_seed: {seed}
    flow_generation_every_n_intervals: {period}
    random_flow_min: "{lo} Gb"
    random_flow_max: "{hi} Gb"
    egress_model: {mode}
    debug_prints: 0
    backpressure_delay_ms: 1.0
    pause_high_watermark_fraction: 0.80
    pause_low_watermark_fraction: 0.50
    terminal_log_path: "logs/terminal-events.csv"
    switch_log_path: "logs/switch-events.csv"
    flowlet_log_path: "logs/flowlet-events.csv"
''')
            cases.append((name, switches, terminals, load, mode, seed, path.relative_to(ROOT),
                          f"topologies/topology-{switches}switch.yaml"))
            pair[mode] = name
        pairs.append((switches, load, pair["pdes"], pair["statistical"]))

with (ROOT / "cases.csv").open("w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "switches", "terminals", "load", "mode", "seed", "config", "topology"])
    w.writerows(cases)
with (ROOT / "pairs.csv").open("w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["switches", "load", "pdes_case", "statistical_case"])
    w.writerows(pairs)
print(f"wrote {len(cases)} Experiment 3 configs ({len(pairs)} matched pairs)")
