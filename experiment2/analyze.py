#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def kv_lines(text: str, prefix: str):
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        fields = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k] = v
        yield fields


def number(fields, names, default=0.0):
    for name in names:
        if name in fields:
            value = float(fields[name])
            if name.endswith("_mbit"):
                value /= 1000.0
            return value
    return default


def percentile(values, q):
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    x = (len(vals) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - x) + vals[hi] * (x - lo)


def jain(values):
    vals = list(values)
    if not vals:
        return 0.0
    ss = sum(v * v for v in vals)
    return (sum(vals) ** 2) / (len(vals) * ss) if ss else 1.0


def top_frac(values, n):
    vals = sorted((max(0.0, x) for x in values), reverse=True)
    total = sum(vals)
    return sum(vals[:n]) / total if total else 0.0


def parse_runtime(text):
    m = re.search(r"Running Time\s*[:=]\s*([0-9.eE+-]+)", text)
    return float(m.group(1)) if m else 0.0


def parse_net_events(text):
    m = re.search(r"Net Events Processed\s+([0-9]+)", text)
    return int(m.group(1)) if m else 0


def parse_config(path: Path):
    text = path.read_text()
    def get(name, default=0.0):
        m = re.search(rf"(?m)^\s*{re.escape(name)}:\s*([0-9.eE+-]+)\s*$", text)
        return float(m.group(1)) if m else default
    return get("interval_seconds", 10.0), int(get("num_send_intervals")), int(get("num_drain_intervals"))


def analyze_case(case, scenario, seed):
    run = ROOT / "results" / scenario / f"seed{seed}" / case / "sync1-np1"
    text = (run / "model-output.log").read_text(errors="replace")
    terminals = list(kv_lines(text, "fluid-flow-wan-terminal "))
    switches = list(kv_lines(text, "fluid-flow-wan gid="))
    if not terminals or not switches:
        raise RuntimeError(f"missing final state summaries in {run}")

    generated = sum(number(t, ("generated_gbit", "generated_mbit")) for t in terminals)
    delivered = sum(number(t, ("received_gbit", "received_mbit")) for t in terminals)
    backlog = sum(number(t, ("source_backlog_gbit", "source_backlog_mbit")) for t in terminals)
    drops = sum(number(s, ("dropped_gbit", "dropped_mbit")) for s in switches)
    residual = sum(number(s, ("shared_buffer_occupied_gbit", "shared_buffer_occupied_mbit",
                              "ready_queue_gbit", "ready_queue_mbit")) for s in switches)
    # shared_buffer_occupied and ready_queue are the same final queued amount in current output;
    # number() intentionally takes the first available key rather than summing both.
    inferred_inflight = generated - delivered - backlog - drops - residual

    interval, send_intervals, drain_intervals = parse_config(run / "config.yaml")
    duration = interval * (send_intervals + drain_intervals)

    terminal_pause_ms = sum(float(t.get("total_pause_time_ms", 0.0)) for t in terminals)
    switch_pause_ms = sum(float(s.get("total_pause_time_ms", 0.0)) for s in switches)
    pause_frames = sum(int(s.get("pause_frames_sent", 0)) for s in switches)
    resume_frames = sum(int(s.get("resume_frames_sent", 0)) for s in switches)

    # Jain fairness across source terminals, including generated sources with zero delivery.
    generated_sources = {int(t["terminal"]) for t in terminals
                         if number(t, ("generated_gbit", "generated_mbit")) > 0}
    delivered_by_source = defaultdict(float)
    term_csv = run / "logs" / "terminal-events.csv"
    with term_csv.open(newline="") as f:
        rd = csv.DictReader(f)
        value_col = "gbit" if "gbit" in (rd.fieldnames or []) else "mbit"
        scale = 1.0 if value_col == "gbit" else .001
        for r in rd:
            if r["event"] == "receive":
                delivered_by_source[int(r["peer_terminal"])] += float(r[value_col]) * scale
    fairness = jain(delivered_by_source.get(s, 0.0) for s in sorted(generated_sources))

    # Queue-drain-time proxy samples and cumulative queue exposure.
    qdrain = []
    queue_by_switch = defaultdict(float)
    sw_csv = run / "logs" / "switch-events.csv"
    with sw_csv.open(newline="") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        unit = "gbit" if any(x.endswith("_gbit") for x in fields) else "mbit"
        scale = 1.0 if unit == "gbit" else .001
        for r in rd:
            if r["event"] != "egress":
                continue
            cap = float(r[f"capacity_{unit}"]) * scale
            queued = float(r[f"queued_after_{unit}"]) * scale
            shared = float(r[f"shared_queued_after_{unit}"]) * scale
            if cap > 0 and queued > 0:
                qdrain.append(queued / (cap / interval))
            queue_by_switch[int(r["switch"])] += max(0.0, shared)

    drop_by_switch = [number(s, ("dropped_gbit", "dropped_mbit")) for s in switches]

    # Flow-specific delivered volume from final-hop switch sends. Used for victim analysis.
    flow_delivered = defaultdict(float)
    fl_csv = run / "logs" / "flowlet-events.csv"
    with fl_csv.open(newline="") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        unit = "gbit" if any(x.endswith("_gbit") for x in fields) else "mbit"
        scale = 1.0 if unit == "gbit" else .001
        for r in rd:
            if r["target_type"] != "terminal" or not r["event"].startswith("allocate_send"):
                continue
            flow_delivered[int(r["flowlet_id"])] += float(r[f"send_{unit}"]) * scale

    victim_gbit = flow_delivered.get(20008, 0.0)
    elephant_values = [flow_delivered.get(20000 + i, 0.0) for i in range(8)]

    return {
        "case": case,
        "scenario": scenario,
        "seed": seed,
        "runtime_sec": parse_runtime(text),
        "net_events": parse_net_events(text),
        "generated_gbit": generated,
        "delivered_gbit": delivered,
        "delivered_goodput_gbps": delivered / duration if duration else 0.0,
        "delivery_fraction": delivered / generated if generated else 0.0,
        "drop_fraction": drops / generated if generated else 0.0,
        "source_backlog_fraction": backlog / generated if generated else 0.0,
        "residual_network_fraction": residual / generated if generated else 0.0,
        "inferred_inflight_gbit": inferred_inflight,
        "qdrain_p50_sec": percentile(qdrain, .50),
        "qdrain_p95_sec": percentile(qdrain, .95),
        "qdrain_p99_sec": percentile(qdrain, .99),
        "terminal_pause_time_ms": terminal_pause_ms,
        "switch_output_pause_time_ms": switch_pause_ms,
        "pause_frames_sent": pause_frames,
        "resume_frames_sent": resume_frames,
        "source_terminal_jain": fairness,
        "queue_top1_fraction": top_frac(queue_by_switch.values(), 1),
        "queue_top5_fraction": top_frac(queue_by_switch.values(), 5),
        "drop_top1_fraction": top_frac(drop_by_switch, 1),
        "drop_top5_fraction": top_frac(drop_by_switch, 5),
        "victim_delivered_gbit": victim_gbit,
        "victim_goodput_gbps": victim_gbit / duration if duration else 0.0,
        "mean_elephant_delivered_gbit": statistics.mean(elephant_values) if any(elephant_values) else 0.0,
    }


def bootstrap_ci(values, reps=10000):
    if len(values) <= 1:
        x = values[0] if values else 0.0
        return x, x, x
    rng = random.Random(12345)
    means = [statistics.mean(rng.choice(values) for _ in values) for _ in range(reps)]
    means.sort()
    return statistics.mean(values), means[int(.025 * (reps - 1))], means[int(.975 * (reps - 1))]


def main():
    cases = []
    with (ROOT / "cases.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            cases.append((r["case"], r["scenario"], int(r["seed"])))
    rows = [analyze_case(*x) for x in cases]

    out = ROOT / "analysis" / "experiment2-summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)

    # Paired three-seed treatment summaries for A/B/C.
    groups = defaultdict(list)
    for r in rows:
        treatment = re.sub(r"-seed\d+$", "", r["case"])
        groups[(r["scenario"], treatment)].append(r)
    metrics = ["delivered_goodput_gbps", "delivery_fraction", "drop_fraction",
               "source_backlog_fraction", "qdrain_p95_sec", "terminal_pause_time_ms",
               "switch_output_pause_time_ms", "source_terminal_jain"]
    agg_rows = []
    for (scenario, treatment), group in sorted(groups.items()):
        rec = {"scenario": scenario, "treatment": treatment, "n": len(group)}
        for metric in metrics:
            mean, lo, hi = bootstrap_ci([float(x[metric]) for x in group])
            rec[f"{metric}_mean"] = mean
            rec[f"{metric}_ci95_low"] = lo
            rec[f"{metric}_ci95_high"] = hi
        agg_rows.append(rec)
    agg = ROOT / "analysis" / "experiment2-aggregate.csv"
    with agg.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg_rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(agg_rows)
    print(f"wrote {out} ({len(rows)} runs)")
    print(f"wrote {agg} ({len(agg_rows)} treatments)")


if __name__ == "__main__":
    main()
