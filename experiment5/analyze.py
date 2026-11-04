#!/usr/bin/env python3
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    results = Path(sys.argv[1])
    runs = list(csv.DictReader((results / "runs.csv").open(newline="")))
    if not runs:
        raise SystemExit("no Experiment 5 runs found")

    baseline = [r for r in runs if r["mode"] == "sequential" and int(r["ranks"]) == 1]
    if not baseline:
        raise SystemExit("missing sequential baseline")

    baseline_runtime = statistics.mean(float(r["runtime_sec"]) for r in baseline)
    baseline_hashes = {r["summary_sha256"] for r in baseline}
    if len(baseline_hashes) != 1:
        raise SystemExit("sequential repeats produced different flow summaries")
    baseline_hash = next(iter(baseline_hashes))

    groups = defaultdict(list)
    for row in runs:
        groups[(row["mode"], int(row["ranks"]))].append(row)

    rows = []
    order = sorted(groups, key=lambda key: (0 if key[0] == "sequential" else 1, key[1]))
    for mode, ranks in order:
        group = groups[(mode, ranks)]
        runtimes = [float(r["runtime_sec"]) for r in group]
        events = [int(r["net_events"]) for r in group]
        runtime_mean = statistics.mean(runtimes)
        speedup = baseline_runtime / runtime_mean
        efficiency = speedup / ranks if mode == "conservative" else 1.0
        parity = all(r["summary_sha256"] == baseline_hash for r in group)

        rows.append(
            {
                "mode": mode,
                "ranks": ranks,
                "repeats": len(group),
                "runtime_sec_mean": runtime_mean,
                "runtime_sec_std": statistics.stdev(runtimes) if len(runtimes) > 1 else 0.0,
                "speedup_vs_sequential": speedup,
                "parallel_efficiency": efficiency,
                "net_events_mean": statistics.mean(events),
                "output_parity": int(parity),
            }
        )

    if not all(row["output_parity"] for row in rows):
        raise SystemExit("one or more conservative runs differ from the sequential flow summary")

    out = results / "experiment5-parallel-scaling-summary.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(out)
    print(",".join(rows[0].keys()))
    for row in rows:
        print(",".join(str(row[k]) for k in rows[0]))


if __name__ == "__main__":
    main()
