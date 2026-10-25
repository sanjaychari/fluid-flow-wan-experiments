#!/usr/bin/env python3
from __future__ import annotations
import csv
import re
from pathlib import Path

DEFAULT_LINK_LATENCY_MS = 5.0

_TIME_SCALE = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "m": 60.0, "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "d": 86400.0, "day": 86400.0, "days": 86400.0,
}


def time_to_seconds(value, unit: str | None = None) -> float:
    """Normalize experiment-facing second/hour/day values to seconds.

    The current CODES flow CSV parser accepts s/ms/us/ns.  Experiment 6 uses
    this helper so workloads can be described naturally in hours/days while
    the emitted CODES CSV remains compatible with the current executable.
    """
    if unit is not None:
        key = unit.strip().lower()
        if key not in _TIME_SCALE:
            raise ValueError(f"unsupported time unit: {unit}")
        return float(value) * _TIME_SCALE[key]
    if isinstance(value, (int, float)):
        return float(value)
    m = re.fullmatch(r"\s*([0-9.eE+-]+)\s*([A-Za-z]+)\s*", str(value))
    if not m:
        raise ValueError(f"invalid time quantity: {value}")
    key = m.group(2).lower()
    if key not in _TIME_SCALE:
        raise ValueError(f"unsupported time unit: {m.group(2)}")
    return float(m.group(1)) * _TIME_SCALE[key]


def write_flow_csv(path: Path, rows) -> None:
    """Write current rate-fluid input CSV.

    rows are (start_time, flow_id, source_terminal, destination_terminal,
    size_gbit). start_time may be a numeric number of seconds or an
    experiment-facing string such as "2 h"/"1 day"; hour/day values are
    normalized to seconds because the current CODES parser does not yet accept
    h/day suffixes directly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["start_time", "flow_id", "source_terminal", "destination_terminal", "size"])
        for start, fid, src, dst, size_gbit in rows:
            start_s = time_to_seconds(start)
            w.writerow([f"{start_s:.12g} s", int(fid), int(src), int(dst), f"{float(size_gbit)/8.0:.12g} GB"])


def write_config(path: Path, *, switches: int, terminals: int, end_time_s: float,
                 topology_file="topology.yaml", flow_file="flows.csv",
                 latency_ms=DEFAULT_LINK_LATENCY_MS, pause_enabled=1,
                 pause_hi=0.80, pause_lo=0.50, debug=0,
                 summary_file="rate-fluid-flow-summary.csv", pe_mem_factor=1024) -> None:
    text = f'''schema_version: 1

topology:
  format: groups
  params:
    message_size: 65536
  groups:
    RATE_FLUID_WAN_GRP:
      repetitions: 1
      lps:
        rate-fluid-wan-switch-lp: {switches}
        rate-fluid-wan-terminal-lp: {terminals}

simulation:
  end_time: "{float(end_time_s):.12g}s"
  pe_mem_factor: {pe_mem_factor}

sections:
  rate_fluid_wan:
    topology_file: "{topology_file}"
    flow_file: "{flow_file}"
    link_latency: "{float(latency_ms):g} ms"
    pause_enabled: {int(pause_enabled)}
    pause_high_watermark_fraction: {float(pause_hi):.6g}
    pause_low_watermark_fraction: {float(pause_lo):.6g}
    debug: {int(debug)}
    flow_summary_file: "{summary_file}"
'''
    path.write_text(text)


def load_summary(path: Path):
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["flow_id"] = int(r["flow_id"])
        r["source_terminal"] = int(r["source_terminal"])
        r["destination_terminal"] = int(r["destination_terminal"])
        r["completed"] = int(r["completed"])
        # Current experiments deliberately emit all flow starts in seconds and
        # all flow sizes in GB, so these are the expected summary fields.
        for k in ("start_s", "size_GB", "received_GB", "finish_s", "fct_s"):
            if k in r and r[k] not in ("", "NA"):
                r[k] = float(r[k])
    return rows
