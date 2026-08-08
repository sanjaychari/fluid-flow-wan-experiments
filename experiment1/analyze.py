#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path

INTERVAL_SECONDS = 0.1
INTERVAL_CAPACITY_GBIT = 20.0
FLOW_SIZES = {1: 500.0, 2: 40.0, 3: 200.0}
EXPECTED_START = {1: 0.0, 2: 0.0, 3: 1.0}
EXPECTED_FINISH = {1: 3.7, 2: 0.4, 3: 3.0}

def find_field(fieldnames, candidates):
    for name in candidates:
        if name in fieldnames:
            return name
    raise RuntimeError(f"none of {candidates} found in fields {fieldnames}")

def analytical_schedule():
    out = defaultdict(lambda: defaultdict(float))
    for i in range(0, 4):
        out[i][1] = 10.0; out[i][2] = 10.0
    for i in range(4, 10): out[i][1] = 20.0
    for i in range(10, 30):
        out[i][1] = 10.0; out[i][3] = 10.0
    for i in range(30, 37): out[i][1] = 20.0
    return out

def load_codes(path: Path):
    absolute = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        switch_field = find_field(fields, ("switch", "switch_id"))
        flow_field = find_field(fields, ("flow_id", "flowlet_id"))
        send_field = find_field(fields, ("send_gbit", "sent_gbit", "send_mbit", "sent_mbit"))
        is_mbit = send_field.endswith("mbit")
        for row in reader:
            if row.get("event") not in ("allocate_send", "allocate_send_arrival", "allocate_send_buffered"):
                continue
            if int(row[switch_field]) != 0:
                continue
            if row.get("target_type") != "terminal" or int(row.get("target_index", -1)) != 3:
                continue
            flow = int(row[flow_field])
            if flow not in FLOW_SIZES:
                continue
            value = float(row[send_field])
            gbit = value / 1000.0 if is_mbit else value
            interval = int(row["interval"])
            absolute[interval][flow] += gbit
            totals[flow] += gbit

    if set(totals) != set(FLOW_SIZES):
        raise RuntimeError(f"missing CODES bottleneck flows: {dict(totals)}")
    for flow, expected in FLOW_SIZES.items():
        if abs(totals[flow] - expected) > 1e-5:
            raise RuntimeError(f"CODES flow {flow} serviced {totals[flow]} Gbit; expected {expected}")

    base = min(absolute)
    relative = defaultdict(lambda: defaultdict(float))
    for interval, values in absolute.items():
        for flow, gbit in values.items():
            relative[interval - base][flow] += gbit
    return relative, base

def load_simgrid(path: Path):
    rows = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            flow = int(row["flow_id"])
            if flow in FLOW_SIZES:
                rows[flow] = {"start": float(row["start_sec"]), "finish": float(row["finish_sec"])}
    if set(rows) != set(FLOW_SIZES):
        raise RuntimeError(f"missing SimGrid flows: {sorted(rows)}")
    return rows

def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: analyze.py fluid-segment-events.csv simgrid-fct.csv interval-comparison.csv")

    expected = analytical_schedule()
    codes, base = load_codes(Path(sys.argv[1]))
    simgrid = load_simgrid(Path(sys.argv[2]))
    detail = Path(sys.argv[3])
    detail.parent.mkdir(parents=True, exist_ok=True)

    max_err = 0.0
    with detail.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["relative_interval", "start_sec", "flow_id", "analytical_gbit", "codes_gbit", "absolute_error_gbit"])
        for interval in range(37):
            for flow in (1, 2, 3):
                exp = expected[interval].get(flow, 0.0)
                act = codes[interval].get(flow, 0.0)
                err = abs(act - exp)
                max_err = max(max_err, err)
                w.writerow([interval, f"{interval * INTERVAL_SECONDS:.1f}", flow,
                            f"{exp:.9f}", f"{act:.9f}", f"{err:.9f}"])

    codes_finish = {}
    for flow in FLOW_SIZES:
        active = [i for i, values in codes.items() if values.get(flow, 0.0) > 1e-12]
        if not active:
            raise RuntimeError(f"no CODES bottleneck service for flow {flow}")
        codes_finish[flow] = (max(active) + 1) * INTERVAL_SECONDS

    codes_finish_err = max(abs(codes_finish[f] - EXPECTED_FINISH[f]) for f in FLOW_SIZES)
    sim_finish_err = max(abs(simgrid[f]["finish"] - EXPECTED_FINISH[f]) for f in FLOW_SIZES)
    sim_start_err = max(abs(simgrid[f]["start"] - EXPECTED_START[f]) for f in FLOW_SIZES)
    pct = 100.0 * max_err / INTERVAL_CAPACITY_GBIT

    print("simulator,max_interval_service_error_gbit,max_interval_service_error_pct,flow1_finish_sec,flow2_finish_sec,flow3_finish_sec,max_finish_error_sec")
    print("Analytical,0.000000000,0.000000000,3.700000000,0.400000000,3.000000000,0.000000000")
    print(f"CODES,{max_err:.9f},{pct:.9f},{codes_finish[1]:.9f},{codes_finish[2]:.9f},{codes_finish[3]:.9f},{codes_finish_err:.9f}")
    print(f"SimGrid,NA,NA,{simgrid[1]['finish']:.9f},{simgrid[2]['finish']:.9f},{simgrid[3]['finish']:.9f},{sim_finish_err:.9f}")
    print(f"# CODES first bottleneck-service interval: {base}", file=sys.stderr)
    print(f"# SimGrid max start-time error: {sim_start_err:.9e} s", file=sys.stderr)

    tol = 1e-6
    if max_err > tol:
        raise SystemExit(f"CODES interval service mismatch: {max_err} Gbit")
    if codes_finish_err > tol:
        raise SystemExit(f"CODES completion mismatch: {codes_finish_err} s")
    if sim_start_err > tol:
        raise SystemExit(f"SimGrid start mismatch: {sim_start_err} s")
    if sim_finish_err > tol:
        raise SystemExit(f"SimGrid completion mismatch: {sim_finish_err} s")

if __name__ == "__main__":
    main()
