#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from fluid_topology import parse_topology  # noqa: E402

INPUTS = ROOT / "inputs"
RUNS = range(1, 9)


def parse_config_int(text: str, key: str) -> int:
    m = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(\d+)\s*$", text)
    if not m:
        raise RuntimeError(f"missing integer config key {key}")
    return int(m.group(1))


def parse_config_float(text: str, key: str) -> float:
    m = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([0-9.eE+-]+)\s*$", text)
    if not m:
        raise RuntimeError(f"missing numeric config key {key}")
    return float(m.group(1))


def main() -> None:
    topology_path = INPUTS / "esnet-fluid-flow-wan-topology.yaml"
    if not topology_path.is_file():
        raise SystemExit(f"missing {topology_path}")

    topo = parse_topology(topology_path)
    if len(topo.switches) != 4 or sum(topo.terminal_counts) != 8:
        raise SystemExit(
            f"unexpected ESNet topology size: {len(topo.switches)} switches, "
            f"{sum(topo.terminal_counts)} terminals"
        )

    total_flows = 0
    for run in RUNS:
        case = INPUTS / f"run{run}"
        config = case / "config.yaml"
        traffic = case / "traffic-trace.csv"
        receiver = case / "receiver-reference.csv"
        physical = case / "physical-summary.csv"

        for p in (config, traffic, receiver, physical):
            if not p.is_file():
                raise SystemExit(f"missing Experiment 1 input: {p}")

        cfg = config.read_text()
        if parse_config_float(cfg, "interval_seconds") != 0.1:
            raise SystemExit(f"run {run}: interval_seconds must be 0.1")
        if parse_config_int(cfg, "num_drain_intervals") != 20:
            raise SystemExit(f"run {run}: expected 20 drain intervals")
        if not re.search(r"(?m)^\s*egress_model:\s*pdes\s*$", cfg):
            raise SystemExit(f"run {run}: expected egress_model: pdes")
        if not re.search(r"(?m)^\s*backpressure_delay_ms:\s*1(?:\.0+)?\s*$", cfg):
            raise SystemExit(f"run {run}: expected 1 ms backpressure delay")

        trace_totals: dict[int, float] = defaultdict(float)
        trace_pairs: dict[int, tuple[int, int]] = {}
        max_interval = -1
        with traffic.open(newline="") as f:
            reader = csv.DictReader(f)
            expected = [
                "interval",
                "flow_id",
                "source_terminal",
                "destination_terminal",
                "offered_gbit",
            ]
            if reader.fieldnames != expected:
                raise SystemExit(f"run {run}: unexpected traffic header {reader.fieldnames}")
            for row in reader:
                interval = int(row["interval"])
                fid = int(row["flow_id"])
                src = int(row["source_terminal"])
                dst = int(row["destination_terminal"])
                gbit = float(row["offered_gbit"])
                if not (0 <= src < 8 and 0 <= dst < 8):
                    raise SystemExit(f"run {run} flow {fid}: terminal outside [0,8)")
                pair = (src, dst)
                if fid in trace_pairs and trace_pairs[fid] != pair:
                    raise SystemExit(f"run {run} flow {fid}: inconsistent source/destination")
                trace_pairs[fid] = pair
                trace_totals[fid] += gbit
                max_interval = max(max_interval, interval)

        send_intervals = parse_config_int(cfg, "num_send_intervals")
        if max_interval + 1 != send_intervals:
            raise SystemExit(
                f"run {run}: max traffic interval is {max_interval}, "
                f"but num_send_intervals is {send_intervals}"
            )

        receiver_totals: dict[int, float] = defaultdict(float)
        with receiver.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                receiver_totals[int(row["flow_id"])] += float(row["received_gbit"])

        physical_rows: dict[int, dict[str, str]] = {}
        with physical.open(newline="") as f:
            for row in csv.DictReader(f):
                physical_rows[int(row["flow_id"])] = row

        if set(trace_totals) != set(receiver_totals) or set(trace_totals) != set(physical_rows):
            raise SystemExit(
                f"run {run}: flow IDs differ across trace/reference/physical summary"
            )

        for fid in sorted(trace_totals):
            p = physical_rows[fid]
            offered = float(p["offered_total_gbit"])
            received = float(p["received_total_gbit"])
            # The committed 100 ms trace uses decimal-rounded per-interval values,
            # so allow a very small reconstruction tolerance.
            if not math.isclose(trace_totals[fid], offered, rel_tol=0.0, abs_tol=0.02):
                raise SystemExit(
                    f"run {run} flow {fid}: traffic total {trace_totals[fid]} "
                    f"!= archived offered total {offered}"
                )
            if not math.isclose(receiver_totals[fid], received, rel_tol=0.0, abs_tol=0.02):
                raise SystemExit(
                    f"run {run} flow {fid}: receiver reference total {receiver_totals[fid]} "
                    f"!= archived received total {received}"
                )

        total_flows += len(trace_totals)
        print(
            f"run {run}: PASS flows={len(trace_totals)} "
            f"send_intervals={send_intervals} trace_rows={sum(1 for _ in traffic.open()) - 1}"
        )

    if total_flows != 12:
        raise SystemExit(f"expected 12 physical flow instances, found {total_flows}")

    print(f"Experiment 1 inputs verified: 8 runs, {total_flows} physical flow instances")


if __name__ == "__main__":
    main()
