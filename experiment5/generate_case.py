#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "common"))

from rate_fluid import DEFAULT_LINK_LATENCY_MS, write_config, write_flow_csv

DEFAULT_SWITCHES = 512
DEFAULT_FLOWS = 4096
TOPOLOGY_SEED = 55005
WORKLOAD_SEED = 55006
START_SPAN_S = 120.0
FLOW_SIZE_GB = (5.0, 20.0)


def write_topology(path: Path, switches: int) -> int:
    rng = random.Random(TOPOLOGY_SEED + switches)
    edges = {i: {(i - 1) % switches, (i + 1) % switches} for i in range(switches)}

    # Add deterministic directed shortcuts while preserving the bidirectional
    # ring, so the graph stays connected for every generated scale.
    target_directed_edges = 4 * switches
    while sum(len(v) for v in edges.values()) < target_directed_edges:
        src = rng.randrange(switches)
        dst = rng.randrange(switches)
        if src != dst:
            edges[src].add(dst)

    lines = ["topology:", "  switches:"]
    for switch in range(switches):
        lines += [
            f"    S{switch}:",
            "      terminals: 2",
            '      terminal_bandwidth: "100 Gbps"',
            '      switch_buffer: "125 GB"',
            "      connections:",
        ]
        for dst in sorted(edges[switch]):
            lines.append(f'        S{dst}: "{rng.uniform(10.0, 30.0):.4f} Gbps"')

    path.write_text("\n".join(lines) + "\n")
    return switches * 2


def build_flows(terminals: int, count: int):
    rng = random.Random(WORKLOAD_SEED + count)
    flows = []

    for flow_id in range(1, count + 1):
        src = rng.randrange(terminals)
        dst = rng.randrange(terminals)
        while dst == src or dst // 2 == src // 2:
            dst = rng.randrange(terminals)

        start = rng.random() * START_SPAN_S
        size_gbit = rng.uniform(*FLOW_SIZE_GB) * 8.0
        flows.append((start, flow_id, src, dst, size_gbit))

    flows.sort(key=lambda row: (row[0], row[1]))
    return flows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case-dir", type=Path, required=True)
    p.add_argument("--switches", type=int, default=DEFAULT_SWITCHES)
    p.add_argument("--flows", type=int, default=DEFAULT_FLOWS)
    p.add_argument("--link-latency-ms", type=float, default=DEFAULT_LINK_LATENCY_MS)
    args = p.parse_args()

    if args.switches < 2:
        raise SystemExit("--switches must be at least 2")
    if args.flows < 1:
        raise SystemExit("--flows must be positive")

    case = args.case_dir
    case.mkdir(parents=True, exist_ok=True)

    terminals = write_topology(case / "topology.yaml", args.switches)
    flows = build_flows(terminals, args.flows)
    write_flow_csv(case / "flows.csv", flows)

    total_gbit = sum(row[4] for row in flows)
    max_start = max(row[0] for row in flows)
    # Deliberately generous. The experiment compares execution modes, not
    # simulated completion time, so all modes must see the same fixed horizon.
    end_time_s = max_start + total_gbit / 10.0 + 120.0

    write_config(
        case / "codes.yaml",
        switches=args.switches,
        terminals=terminals,
        end_time_s=end_time_s,
        latency_ms=args.link_latency_ms,
        pause_enabled=0,
        debug=0,
    )

    starts = [row[0] for row in flows]
    with (case / "workload-metadata.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "switches",
                "terminals",
                "flows",
                "start_span_s",
                "offered_GB",
                "link_latency_ms",
                "topology_seed",
                "workload_seed",
            ]
        )
        w.writerow(
            [
                args.switches,
                terminals,
                len(flows),
                f"{max(starts) - min(starts):.9f}",
                f"{total_gbit / 8.0:.9f}",
                f"{args.link_latency_ms:.9f}",
                TOPOLOGY_SEED,
                WORKLOAD_SEED,
            ]
        )

    print(
        f"switches={args.switches} terminals={terminals} flows={len(flows)} "
        f"start_span_s={max(starts) - min(starts):.6f} "
        f"offered_GB={total_gbit / 8.0:.6f}"
    )


if __name__ == "__main__":
    main()
