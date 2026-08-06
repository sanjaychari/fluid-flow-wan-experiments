#!/usr/bin/env python3

import csv
import sys
from collections import defaultdict
from pathlib import Path


EXPECTED_RATE_GBPS = 5.0
FLOW_SIZE_GBIT = 10.0
INTERVAL_SECONDS = 1.0


def find_field(fieldnames, candidates):
    for name in candidates:
        if name in fieldnames:
            return name
    raise RuntimeError(
        f"none of {candidates} found in CSV fields {fieldnames}"
    )


def codes_rates(path: Path):
    by_interval = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        switch_field = find_field(fields, ("switch", "switch_id"))
        flow_field = find_field(fields, ("flow_id", "flowlet_id"))
        send_field = find_field(
            fields,
            ("send_gbit", "sent_gbit", "send_mbit", "sent_mbit"),
        )

        is_mbit = send_field.endswith("mbit")

        for row in reader:
            if row["event"] not in (
                "allocate_send",
                "allocate_send_arrival",
                "allocate_send_buffered",
            ):
                continue

            # S0 is switch 0, and S1 is switch 1.
            if int(row[switch_field]) != 0:
                continue
            if row["target_type"] != "switch":
                continue
            if int(row["target_index"]) != 1:
                continue

            flow = int(row[flow_field])
            if flow not in (1, 2):
                continue

            value = float(row[send_field])
            gbit = value / 1000.0 if is_mbit else value

            interval = int(row["interval"])
            by_interval[interval][flow] += gbit
            totals[flow] += gbit

    if set(totals) != {1, 2}:
        raise RuntimeError(f"missing CODES bottleneck flows: {dict(totals)}")

    # Both complete flows must cross the bottleneck.
    for flow in (1, 2):
        if abs(totals[flow] - FLOW_SIZE_GBIT) > 1e-5:
            raise RuntimeError(
                f"CODES flow {flow} sent {totals[flow]} Gbit "
                f"across bottleneck; expected {FLOW_SIZE_GBIT}"
            )

    # Find the first service interval in which both flows are simultaneously
    # present. Max-min fairness should give exactly 5 Gbit to each in 1 second.
    for interval in sorted(by_interval):
        values = by_interval[interval]
        if values.get(1, 0.0) > 0 and values.get(2, 0.0) > 0:
            return (
                values[1] / INTERVAL_SECONDS,
                values[2] / INTERVAL_SECONDS,
                interval,
            )

    raise RuntimeError("no common CODES bottleneck service interval found")


def simgrid_rates(path: Path):
    rates = {}

    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            flow = int(row["flow_id"])
            if flow not in (1, 2):
                continue
            fct = float(row["fct_sec"])
            rates[flow] = FLOW_SIZE_GBIT / fct

    if set(rates) != {1, 2}:
        raise RuntimeError(f"missing SimGrid flows: {rates}")

    return rates[1], rates[2]


def max_error_pct(r1, r2):
    return 100.0 * max(
        abs(r1 - EXPECTED_RATE_GBPS) / EXPECTED_RATE_GBPS,
        abs(r2 - EXPECTED_RATE_GBPS) / EXPECTED_RATE_GBPS,
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: analyze_correctness.py "
            "fluid-segment-events.csv simgrid-fct.csv"
        )

    c1, c2, interval = codes_rates(Path(sys.argv[1]))
    s1, s2 = simgrid_rates(Path(sys.argv[2]))

    print(
        "simulator,flow1_rate_gbps,flow2_rate_gbps,"
        "max_relative_error_pct"
    )
    print(
        f"Analytical,{EXPECTED_RATE_GBPS:.9f},"
        f"{EXPECTED_RATE_GBPS:.9f},0.000000000"
    )
    print(
        f"CODES,{c1:.9f},{c2:.9f},"
        f"{max_error_pct(c1, c2):.9f}"
    )
    print(
        f"SimGrid,{s1:.9f},{s2:.9f},"
        f"{max_error_pct(s1, s2):.9f}"
    )

    print(
        f"# CODES common bottleneck service interval: {interval}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
