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
RESULTS = ROOT / "results"
ANALYSIS = ROOT / "analysis"
REFERENCE = ROOT / "reference-results" / "validation-summary.csv"
INTERVAL_SECONDS = 0.1
VOLUME_THRESHOLD = 0.01
NMAE_THRESHOLD = 0.10
TOL = 1e-6


def parse_key_values(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in line.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        out[key] = value
    return out


def load_flow_metadata(run_dir: Path) -> dict[int, dict[str, object]]:
    physical: dict[int, dict[str, str]] = {}
    with (run_dir / "physical-summary.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            physical[int(row["flow_id"])] = row

    pairs: dict[int, tuple[int, int]] = {}
    first_interval: dict[int, int] = {}
    with (run_dir / "traffic-trace.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            fid = int(row["flow_id"])
            pair = (int(row["source_terminal"]), int(row["destination_terminal"]))
            if fid in pairs and pairs[fid] != pair:
                raise RuntimeError(f"flow {fid} changes source/destination")
            pairs[fid] = pair
            first_interval[fid] = min(first_interval.get(fid, 10**18), int(row["interval"]))

    observed: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    with (run_dir / "receiver-reference.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            fid = int(row["flow_id"])
            # The archived reference is exactly one-second bins with integer boundaries.
            sec = int(round(float(row["start_seconds"])))
            observed[fid][sec] += float(row["received_gbit"])

    if set(physical) != set(pairs) or set(physical) != set(observed):
        raise RuntimeError(f"inconsistent flow IDs in {run_dir}")

    out: dict[int, dict[str, object]] = {}
    for fid, p in physical.items():
        src, dst = pairs[fid]
        out[fid] = {
            "flow_id": fid,
            "source_terminal": src,
            "destination_terminal": dst,
            "label": p["label"],
            "start_seconds": float(p["start_seconds"]),
            "first_interval": first_interval[fid],
            "physical_offered_gbit": float(p["offered_total_gbit"]),
            "physical_received_gbit": float(p["received_total_gbit"]),
            "observed": observed[fid],
        }
    return out


def load_codes_receive(run_dir: Path) -> dict[tuple[int, int], list[tuple[int, float]]]:
    path = run_dir / "logs" / "terminal-events.csv"
    if not path.is_file():
        raise RuntimeError(f"missing CODES terminal log: {path}")

    events: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "gbit" in fields:
            value_col = "gbit"
            scale = 1.0
        elif "mbit" in fields:
            value_col = "mbit"
            scale = 0.001
        else:
            raise RuntimeError(f"cannot find gbit/mbit column in {path}")

        for row in reader:
            if row["event"] != "receive":
                continue
            src = int(row["peer_terminal"])
            dst = int(row["terminal"])
            events[(src, dst)].append(
                (int(row["interval"]), float(row[value_col]) * scale)
            )
    return events


def bin_events(events: list[tuple[int, float]], shift_intervals: int) -> dict[int, float]:
    bins: dict[int, float] = defaultdict(float)
    for interval, gbit in events:
        # shift_intervals is subtracted so model pipeline delay is removed before
        # comparing with the physical receiver's one-second bins.
        sec = math.floor((interval - shift_intervals) * INTERVAL_SECONDS + 1e-12)
        bins[sec] += gbit
    return bins


def nmae(sim: dict[int, float], obs: dict[int, float]) -> float:
    total = sum(obs.values())
    if total == 0.0:
        return 0.0
    seconds = set(sim) | set(obs)
    return sum(abs(sim.get(s, 0.0) - obs.get(s, 0.0)) for s in seconds) / total


def end_state(model_output: Path) -> dict[str, float | int]:
    terminals = 0
    switches = 0
    source_backlog = 0.0
    ready_queue = 0.0
    occupied = 0.0
    dropped = 0.0
    pause_ms = 0.0

    for line in model_output.read_text(errors="replace").splitlines():
        if line.startswith("fluid-flow-wan-terminal "):
            terminals += 1
            fields = parse_key_values(line)
            source_backlog += float(fields.get("source_backlog_gbit", "0"))
            pause_ms += float(fields.get("total_pause_time_ms", "0"))
        elif line.startswith("fluid-flow-wan gid="):
            switches += 1
            fields = parse_key_values(line)
            ready_queue += float(fields.get("ready_queue_gbit", "0"))
            occupied += float(fields.get("shared_buffer_occupied_gbit", "0"))
            dropped += float(fields.get("dropped_gbit", "0"))
            pause_ms += float(fields.get("total_pause_time_ms", "0"))

    if terminals == 0 or switches == 0:
        raise RuntimeError(f"missing terminal/switch summaries in {model_output}")

    return {
        "terminal_summaries": terminals,
        "switch_summaries": switches,
        "source_backlog_gbit": source_backlog,
        "ready_queue_gbit": ready_queue,
        "shared_buffer_occupied_gbit": occupied,
        "dropped_gbit": dropped,
        "total_pause_time_ms": pause_ms,
    }


def write_validation_text(
    run: int,
    run_dir: Path,
    flow_rows: list[dict[str, object]],
    physical_total: float,
    codes_total: float,
) -> None:
    lines = [f"Run directory: {run_dir}", "Mode: pdes", ""]
    for row in flow_rows:
        lines += [
            f"flow {row['flow_id']}: {row['label']}",
            f"  physical offered total : {row['physical_offered_gbit']:.6f} Gbit",
            f"  physical received total: {row['physical_received_gbit']:.6f} Gbit",
            f"  CODES received total   : {row['codes_received_gbit']:.6f} Gbit",
            f"  total-volume error     : {row['signed_volume_error_pct']:+.4f}%",
            f"  1-s NMAE raw           : {row['raw_1s_nmae_pct']:.4f}%",
            f"  1-s NMAE delay-adjusted: {row['delay_adjusted_1s_nmae_pct']:.4f}%",
            f"  modeled delay removed  : {row['delay_adjust_intervals']} intervals "
            f"({row['delay_adjust_seconds']:.1f} s)",
            "",
        ]
    agg = 100.0 * (codes_total - physical_total) / physical_total if physical_total else 0.0
    lines += [
        f"aggregate physical received: {physical_total:.6f} Gbit",
        f"aggregate CODES received   : {codes_total:.6f} Gbit",
        f"aggregate volume error     : {agg:+.4f}%",
    ]
    (run_dir / "validation.txt").write_text("\n".join(lines) + "\n")


def main() -> None:
    topology = parse_topology(INPUTS / "esnet-fluid-flow-wan-topology.yaml")
    terminal_to_switch = topology.terminal_to_switch

    available_runs = [
        run for run in range(1, 9)
        if (RESULTS / f"run{run}" / "model-output.log").is_file()
    ]
    if not available_runs:
        raise SystemExit("no Experiment 1 outputs found under experiment1/results/")

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    flow_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []

    for run in available_runs:
        run_dir = RESULTS / f"run{run}"
        meta = load_flow_metadata(run_dir)
        receives = load_codes_receive(run_dir)
        state = end_state(run_dir / "model-output.log")

        this_flow_rows: list[dict[str, object]] = []
        for fid in sorted(meta):
            info = meta[fid]
            src = int(info["source_terminal"])
            dst = int(info["destination_terminal"])
            pair = (src, dst)
            events = receives.get(pair, [])
            if not events:
                raise RuntimeError(f"run {run} flow {fid}: no CODES receive events for {src}->{dst}")

            src_switch = terminal_to_switch[src]
            dst_switch = terminal_to_switch[dst]
            switch_path = topology.bfs_path(src_switch, dst_switch)
            switch_hops = len(switch_path) - 1
            delay_intervals = 2 + switch_hops

            raw_bins = bin_events(events, 0)
            adjusted_bins = bin_events(events, delay_intervals)
            obs = info["observed"]
            assert isinstance(obs, dict)

            codes_total = sum(g for _, g in events)
            physical_received = float(info["physical_received_gbit"])
            signed_error = (
                (codes_total - physical_received) / physical_received
                if physical_received else 0.0
            )
            raw = nmae(raw_bins, obs)
            adjusted = nmae(adjusted_bins, obs)

            row: dict[str, object] = {
                "run": run,
                "flow_id": fid,
                "label": info["label"],
                "source_terminal": src,
                "destination_terminal": dst,
                "switch_path": "->".join(topology.switches[s] for s in switch_path),
                "switch_hops": switch_hops,
                "delay_adjust_intervals": delay_intervals,
                "delay_adjust_seconds": delay_intervals * INTERVAL_SECONDS,
                "physical_offered_gbit": float(info["physical_offered_gbit"]),
                "physical_received_gbit": physical_received,
                "codes_received_gbit": codes_total,
                "signed_volume_error_pct": 100.0 * signed_error,
                "absolute_volume_error_pct": 100.0 * abs(signed_error),
                "raw_1s_nmae_pct": 100.0 * raw,
                "delay_adjusted_1s_nmae_pct": 100.0 * adjusted,
                "volume_pass": int(abs(signed_error) <= VOLUME_THRESHOLD),
                "nmae_pass": int(adjusted <= NMAE_THRESHOLD),
            }
            flow_rows.append(row)
            this_flow_rows.append(row)

        physical_total = sum(float(r["physical_received_gbit"]) for r in this_flow_rows)
        codes_total = sum(float(r["codes_received_gbit"]) for r in this_flow_rows)
        agg_error = (codes_total - physical_total) / physical_total if physical_total else 0.0

        state_pass = (
            abs(float(state["source_backlog_gbit"])) <= TOL
            and abs(float(state["ready_queue_gbit"])) <= TOL
            and abs(float(state["shared_buffer_occupied_gbit"])) <= TOL
            and abs(float(state["dropped_gbit"])) <= TOL
        )

        run_rows.append({
            "run": run,
            "flows": len(this_flow_rows),
            "physical_received_gbit": physical_total,
            "codes_received_gbit": codes_total,
            "aggregate_signed_volume_error_pct": 100.0 * agg_error,
            "source_backlog_gbit": float(state["source_backlog_gbit"]),
            "ready_queue_gbit": float(state["ready_queue_gbit"]),
            "shared_buffer_occupied_gbit": float(state["shared_buffer_occupied_gbit"]),
            "dropped_gbit": float(state["dropped_gbit"]),
            "total_pause_time_ms": float(state["total_pause_time_ms"]),
            "end_state_pass": int(state_pass),
        })

        write_validation_text(run, run_dir, this_flow_rows, physical_total, codes_total)

    detailed = ANALYSIS / "experiment1-flow-summary.csv"
    with detailed.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flow_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(flow_rows)

    run_summary = ANALYSIS / "experiment1-run-summary.csv"
    with run_summary.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(run_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(run_rows)

    # Compact summary with the same schema/rounding as the archived artifact.
    validation_summary = ANALYSIS / "validation-summary.csv"
    with validation_summary.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["run", "flow_id", "label", "volume_error_pct", "nmae_pct"])
        for row in flow_rows:
            w.writerow([
                row["run"],
                row["flow_id"],
                row["label"],
                f"{float(row['absolute_volume_error_pct']):.4f}".rstrip("0").rstrip("."),
                f"{float(row['delay_adjusted_1s_nmae_pct']):.4f}".rstrip("0").rstrip("."),
            ])

    max_volume = max(float(r["absolute_volume_error_pct"]) for r in flow_rows)
    max_nmae = max(float(r["delay_adjusted_1s_nmae_pct"]) for r in flow_rows)
    max_backlog = max(abs(float(r["source_backlog_gbit"])) for r in run_rows)
    max_ready = max(abs(float(r["ready_queue_gbit"])) for r in run_rows)
    max_occupied = max(abs(float(r["shared_buffer_occupied_gbit"])) for r in run_rows)
    total_drops = sum(float(r["dropped_gbit"]) for r in run_rows)
    complete = available_runs == list(range(1, 9)) and len(flow_rows) == 12
    passed = (
        complete
        and max_volume <= 100.0 * VOLUME_THRESHOLD
        and max_nmae <= 100.0 * NMAE_THRESHOLD
        and max_backlog <= TOL
        and max_ready <= TOL
        and max_occupied <= TOL
        and abs(total_drops) <= TOL
    )

    headline = ANALYSIS / "experiment1-headline.csv"
    with headline.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([
            "runs",
            "flows",
            "complete_matrix",
            "max_whole_run_relative_error_pct",
            "max_delay_adjusted_1s_nmae_pct",
            "max_source_backlog_gbit",
            "max_ready_queue_gbit",
            "max_shared_buffer_occupied_gbit",
            "total_dropped_gbit",
            "volume_threshold_pct",
            "nmae_threshold_pct",
            "pass",
        ])
        w.writerow([
            len(available_runs),
            len(flow_rows),
            int(complete),
            f"{max_volume:.6f}",
            f"{max_nmae:.6f}",
            f"{max_backlog:.9f}",
            f"{max_ready:.9f}",
            f"{max_occupied:.9f}",
            f"{total_drops:.9f}",
            "1.0",
            "10.0",
            int(passed),
        ])

    if REFERENCE.is_file():
        ref: dict[tuple[int, int], tuple[float, float]] = {}
        with REFERENCE.open(newline="") as f:
            for row in csv.DictReader(f):
                ref[(int(row["run"]), int(row["flow_id"]))] = (
                    float(row["volume_error_pct"]),
                    float(row["nmae_pct"]),
                )
        comparison = ANALYSIS / "reference-comparison.csv"
        with comparison.open("w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow([
                "run",
                "flow_id",
                "current_volume_error_pct",
                "archived_volume_error_pct",
                "current_nmae_pct",
                "archived_nmae_pct",
            ])
            for row in flow_rows:
                key = (int(row["run"]), int(row["flow_id"]))
                if key not in ref:
                    continue
                rv, rn = ref[key]
                w.writerow([
                    key[0],
                    key[1],
                    f"{float(row['absolute_volume_error_pct']):.6f}",
                    f"{rv:.6f}",
                    f"{float(row['delay_adjusted_1s_nmae_pct']):.6f}",
                    f"{rn:.6f}",
                ])

    print(headline.read_text(), end="")
    if complete:
        print(f"flow summary: {detailed}")
        print(f"run summary : {run_summary}")
        print(f"reference   : {ANALYSIS / 'reference-comparison.csv'}")


if __name__ == "__main__":
    main()
