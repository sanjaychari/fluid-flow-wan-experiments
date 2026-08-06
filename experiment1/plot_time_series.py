#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "common"))

from fluid_topology import parse_topology  # noqa: E402


INTERVAL_SECONDS = 0.1


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    return text.strip("-") or "flow"


def load_flow_metadata(run_dir: Path) -> dict[int, dict[str, object]]:
    physical_path = run_dir / "physical-summary.csv"
    trace_path = run_dir / "traffic-trace.csv"
    reference_path = run_dir / "receiver-reference.csv"

    for path in (physical_path, trace_path, reference_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required file: {path}")

    physical: dict[int, dict[str, str]] = {}
    with physical_path.open(newline="") as f:
        for row in csv.DictReader(f):
            physical[int(row["flow_id"])] = row

    pairs: dict[int, tuple[int, int]] = {}
    with trace_path.open(newline="") as f:
        for row in csv.DictReader(f):
            flow_id = int(row["flow_id"])
            pair = (
                int(row["source_terminal"]),
                int(row["destination_terminal"]),
            )

            if flow_id in pairs and pairs[flow_id] != pair:
                raise RuntimeError(
                    f"Flow {flow_id} changes terminal pair: "
                    f"{pairs[flow_id]} versus {pair}"
                )

            pairs[flow_id] = pair

    observed: dict[int, dict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    with reference_path.open(newline="") as f:
        for row in csv.DictReader(f):
            flow_id = int(row["flow_id"])
            second = int(round(float(row["start_seconds"])))
            observed[flow_id][second] += float(row["received_gbit"])

    expected_ids = set(physical)
    if expected_ids != set(pairs):
        raise RuntimeError(
            f"Flow IDs differ between {physical_path} and {trace_path}"
        )
    if expected_ids != set(observed):
        raise RuntimeError(
            f"Flow IDs differ between {physical_path} and {reference_path}"
        )

    metadata: dict[int, dict[str, object]] = {}

    for flow_id in sorted(expected_ids):
        src, dst = pairs[flow_id]
        row = physical[flow_id]

        metadata[flow_id] = {
            "flow_id": flow_id,
            "source_terminal": src,
            "destination_terminal": dst,
            "label": row.get("label", f"flow {flow_id}"),
            "observed": dict(observed[flow_id]),
        }

    return metadata


def load_codes_receive_events(
    run_dir: Path,
) -> dict[tuple[int, int], list[tuple[int, float]]]:
    path = run_dir / "logs" / "terminal-events.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing CODES terminal log: {path}")

    events: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        if "gbit" in fields:
            value_column = "gbit"
            scale = 1.0
        elif "mbit" in fields:
            value_column = "mbit"
            scale = 0.001
        else:
            raise RuntimeError(
                f"{path} has neither a gbit nor an mbit column"
            )

        required = {
            "event",
            "terminal",
            "peer_terminal",
            "interval",
            value_column,
        }
        missing = required - set(fields)
        if missing:
            raise RuntimeError(
                f"{path} is missing columns: {sorted(missing)}"
            )

        for row in reader:
            if row["event"] != "receive":
                continue

            source_terminal = int(row["peer_terminal"])
            destination_terminal = int(row["terminal"])
            interval = int(row["interval"])
            gbit = float(row[value_column]) * scale

            events[(source_terminal, destination_terminal)].append(
                (interval, gbit)
            )

    return events


def bin_codes_events(
    events: list[tuple[int, float]],
    shift_intervals: int,
) -> dict[int, float]:
    bins: dict[int, float] = defaultdict(float)

    for interval, gbit in events:
        shifted_time = (interval - shift_intervals) * INTERVAL_SECONDS
        second = math.floor(shifted_time + 1e-12)

        # Do not plot pre-zero bins created by delay correction.
        if second >= 0:
            bins[second] += gbit

    return dict(bins)


def aligned_series(
    physical: dict[int, float],
    raw_codes: dict[int, float],
    adjusted_codes: dict[int, float],
) -> tuple[list[int], list[float], list[float], list[float]]:
    all_seconds = set(physical) | set(raw_codes) | set(adjusted_codes)

    if not all_seconds:
        return [], [], [], []

    first = min(all_seconds)
    last = max(all_seconds)
    seconds = list(range(first, last + 1))

    return (
        seconds,
        [physical.get(second, 0.0) for second in seconds],
        [raw_codes.get(second, 0.0) for second in seconds],
        [adjusted_codes.get(second, 0.0) for second in seconds],
    )


def plot_flow(
    *,
    run: int,
    flow_id: int,
    label: str,
    source_terminal: int,
    destination_terminal: int,
    switch_path: list[int],
    switch_names: list[str],
    delay_intervals: int,
    physical: dict[int, float],
    raw_codes: dict[int, float],
    adjusted_codes: dict[int, float],
    output_path: Path,
    dpi: int,
) -> None:
    seconds, physical_y, raw_y, adjusted_y = aligned_series(
        physical,
        raw_codes,
        adjusted_codes,
    )

    if not seconds:
        raise RuntimeError(f"Run {run}, flow {flow_id} has no plot data")

    figure, axis = plt.subplots(figsize=(10.5, 5.5))

    axis.plot(
        seconds,
        physical_y,
        linewidth=1.8,
        label="ESnet receiver reference",
    )
    axis.plot(
        seconds,
        raw_y,
        linewidth=1.3,
        linestyle="--",
        label="CODES receiver output (raw)",
    )
    axis.plot(
        seconds,
        adjusted_y,
        linewidth=1.5,
        linestyle="-.",
        label="CODES receiver output (delay-adjusted)",
    )

    path_text = " → ".join(switch_names[index] for index in switch_path)
    delay_seconds = delay_intervals * INTERVAL_SECONDS

    axis.set_title(
        f"Experiment 1, run {run}: {label}\n"
        f"flow {flow_id}, terminal {source_terminal} → "
        f"{destination_terminal}, path {path_text}"
    )
    axis.set_xlabel("Time (seconds)")
    axis.set_ylabel("Received data per one-second bin (Gbit)")
    axis.grid(True, alpha=0.3)
    axis.legend(
        title=(
            f"Delay adjustment: {delay_intervals} intervals "
            f"({delay_seconds:.1f} s)"
        )
    )

    figure.tight_layout()
    figure.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(figure)


def create_combined_plot(
    plot_rows: list[dict[str, object]],
    output_path: Path,
    dpi: int,
) -> None:
    if not plot_rows:
        return

    columns = 2
    rows = math.ceil(len(plot_rows) / columns)

    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(15, max(4.0 * rows, 6.0)),
        squeeze=False,
    )

    flat_axes = list(axes.flat)

    for axis, item in zip(flat_axes, plot_rows):
        seconds = item["seconds"]
        physical_y = item["physical_y"]
        raw_y = item["raw_y"]
        adjusted_y = item["adjusted_y"]

        assert isinstance(seconds, list)
        assert isinstance(physical_y, list)
        assert isinstance(raw_y, list)
        assert isinstance(adjusted_y, list)

        axis.plot(
            seconds,
            physical_y,
            linewidth=1.5,
            label="ESnet reference",
        )
        axis.plot(
            seconds,
            raw_y,
            linewidth=1.1,
            linestyle="--",
            label="CODES raw",
        )
        axis.plot(
            seconds,
            adjusted_y,
            linewidth=1.2,
            linestyle="-.",
            label="CODES adjusted",
        )

        axis.set_title(
            f"Run {item['run']}, flow {item['flow_id']}: "
            f"{item['label']}",
            fontsize=10,
        )
        axis.set_xlabel("Time (s)")
        axis.set_ylabel("Received Gbit / 1 s")
        axis.grid(True, alpha=0.3)

    for axis in flat_axes[len(plot_rows):]:
        axis.set_visible(False)

    handles, labels = flat_axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.5, 0.995),
    )
    figure.suptitle(
        "Experiment 1: ESnet reference and CODES receiver time series",
        y=1.01,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.98))
    figure.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plot Experiment 1 ESnet receiver reference data against "
            "raw and delay-adjusted CODES receiver output."
        )
    )
    parser.add_argument(
        "--run",
        type=int,
        action="append",
        dest="runs",
        help=(
            "Run number to plot. Repeat this option for multiple runs. "
            "By default, all available run1 through run8 directories are used."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "analysis" / "time-series-plots",
        help="Directory for generated plots.",
    )
    parser.add_argument(
        "--format",
        choices=("png", "pdf", "svg"),
        default="png",
        help="Output plot format.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=220,
        help="Raster output resolution.",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help=(
            "Accepted for command-line compatibility. The individual plots "
            "currently include raw and adjusted CODES curves."
        ),
    )
    args = parser.parse_args()

    topology_path = (
        SCRIPT_DIR / "inputs" / "esnet-fluid-flow-wan-topology.yaml"
    )
    if not topology_path.is_file():
        raise FileNotFoundError(f"Missing topology: {topology_path}")

    topology = parse_topology(topology_path)
    terminal_to_switch = topology.terminal_to_switch

    if args.runs:
        runs = sorted(set(args.runs))
    else:
        runs = [
            run
            for run in range(1, 9)
            if (SCRIPT_DIR / "results" / f"run{run}").is_dir()
        ]

    if not runs:
        raise SystemExit(
            "No Experiment 1 runs found under experiment1/results/"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    combined_rows: list[dict[str, object]] = []

    for run in runs:
        run_dir = SCRIPT_DIR / "results" / f"run{run}"
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Missing run directory: {run_dir}")

        metadata = load_flow_metadata(run_dir)
        codes_events = load_codes_receive_events(run_dir)

        run_output_dir = args.output_dir / f"run{run}"
        run_output_dir.mkdir(parents=True, exist_ok=True)

        for flow_id in sorted(metadata):
            info = metadata[flow_id]

            source_terminal = int(info["source_terminal"])
            destination_terminal = int(info["destination_terminal"])
            pair = (source_terminal, destination_terminal)

            events = codes_events.get(pair, [])
            if not events:
                raise RuntimeError(
                    f"Run {run}, flow {flow_id}: no CODES receiver events "
                    f"for terminal pair {source_terminal}->{destination_terminal}"
                )

            source_switch = terminal_to_switch[source_terminal]
            destination_switch = terminal_to_switch[destination_terminal]
            switch_path = topology.bfs_path(
                source_switch,
                destination_switch,
            )

            switch_hops = len(switch_path) - 1
            delay_intervals = 2 + switch_hops

            physical = info["observed"]
            assert isinstance(physical, dict)

            raw_codes = bin_codes_events(events, shift_intervals=0)
            adjusted_codes = bin_codes_events(
                events,
                shift_intervals=delay_intervals,
            )

            label = str(info["label"])
            filename = (
                f"run{run}-flow{flow_id}-"
                f"{safe_filename(label)}.{args.format}"
            )
            output_path = run_output_dir / filename

            plot_flow(
                run=run,
                flow_id=flow_id,
                label=label,
                source_terminal=source_terminal,
                destination_terminal=destination_terminal,
                switch_path=switch_path,
                switch_names=topology.switches,
                delay_intervals=delay_intervals,
                physical=physical,
                raw_codes=raw_codes,
                adjusted_codes=adjusted_codes,
                output_path=output_path,
                dpi=args.dpi,
            )

            seconds, physical_y, raw_y, adjusted_y = aligned_series(
                physical,
                raw_codes,
                adjusted_codes,
            )

            combined_rows.append(
                {
                    "run": run,
                    "flow_id": flow_id,
                    "label": label,
                    "seconds": seconds,
                    "physical_y": physical_y,
                    "raw_y": raw_y,
                    "adjusted_y": adjusted_y,
                }
            )

            print(f"Wrote {output_path}")

    combined_path = (
        args.output_dir
        / f"experiment1-all-flows.{args.format}"
    )
    create_combined_plot(
        combined_rows,
        combined_path,
        args.dpi,
    )
    print(f"Wrote {combined_path}")


if __name__ == "__main__":
    main()
