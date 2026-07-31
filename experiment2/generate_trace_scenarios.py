#!/usr/bin/env python3
from __future__ import annotations

import csv
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "common"))
from fluid_topology import parse_topology  # noqa: E402

TOPO = ROOT / "topologies" / "topology-buffer100Gb.yaml"
OUT = ROOT / "traces"
OUT.mkdir(parents=True, exist_ok=True)


def write_trace(path: Path, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["interval", "flow_id", "source_terminal", "destination_terminal", "offered_gbit"])
        w.writerows(rows)


def main() -> None:
    topo = parse_topology(TOPO)
    nterm = len(topo.terminal_to_switch)

    # C: persistent incast.  Each source offers 100 Gbit every 10 s (=10 Gbps).
    for fanin in (4, 8, 16):
        for seed in range(2001, 2011):
            rng = random.Random(seed * 100 + fanin)
            sources = rng.sample(list(range(1, nterm)), fanin)
            rows = []
            flow_meta = []
            for i, src in enumerate(sources):
                fid = 10000 + fanin * 100 + seed * 20 + i
                flow_meta.append((fid, src, 0, "incast"))
                for interval in range(20):
                    rows.append((interval, fid, src, 0, "100.000000"))
            name = f"incast-{fanin}-seed{seed}"
            write_trace(OUT / f"{name}.csv", rows)
            with (OUT / f"{name}-metadata.csv").open("w", newline="") as f:
                w = csv.writer(f, lineterminator="\n")
                w.writerow(["flow_id", "source_terminal", "destination_terminal", "label"])
                w.writerows(flow_meta)

    # D: guarantee that every flow traverses the known low-rate S45->S44 edge.
    s45 = topo.terminals_on_switch("S45")[0]
    s44 = topo.terminals_on_switch("S44")[0]
    edge = topo.edge_mbps[(topo.switch_index["S45"], topo.switch_index["S44"])] / 1000.0
    if abs(edge - 10.0637) > 0.01:
        raise SystemExit(f"unexpected S45->S44 rate: {edge} Gbps")

    rows = []
    meta = []
    for i in range(8):
        fid = 20000 + i
        meta.append((fid, s45, s44, "elephant"))
        for interval in range(40):
            rows.append((interval, fid, s45, s44, "75.000000"))  # 7.5 Gbps
    victim = 20008
    meta.append((victim, s45, s44, "victim"))
    for interval in range(40):
        rows.append((interval, victim, s45, s44, "10.000000"))  # 1 Gbps

    for mode in ("asymmetric", "symmetric"):
        write_trace(OUT / f"victim-{mode}.csv", rows)
        with (OUT / f"victim-{mode}-metadata.csv").open("w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["flow_id", "source_terminal", "destination_terminal", "label"])
            w.writerows(meta)

    # The base generated topology has S45->S44 ~=10.0637 Gbps and S44->S45
    # ~=20.7424 Gbps.  The paired symmetric case changes only that reverse
    # edge's bandwidth, leaving graph structure and all other rates fixed.
    base = TOPO.read_text()
    match = re.search(r'(?ms)(^    S44:\n.*?^      connections:\n)(.*?)(?=^    \S|\Z)', base)
    if not match:
        raise SystemExit("could not locate S44 block")
    block = match.group(0)
    new_block, count = re.subn(r'(^        S45:\s*")[^"]+("\s*$)', r'\g<1>10.0637 Gbps\2', block, flags=re.M)
    if count != 1:
        raise SystemExit("could not uniquely change S44->S45 reverse bandwidth")
    symmetric = base[: match.start()] + new_block + base[match.end() :]
    # Asymmetric-connectivity pair: remove only the direct S44->S45 reverse edge.
    asym_block, removed = re.subn(r'^        S45:\s*"[^"]+"\s*\n', '', block, count=1, flags=re.M)
    if removed != 1:
        raise SystemExit("could not uniquely remove S44->S45 reverse edge")
    asymmetric = base[: match.start()] + asym_block + base[match.end() :]
    (ROOT / "topologies" / "topology-victim-symmetric.yaml").write_text(symmetric)
    (ROOT / "topologies" / "topology-victim-asymmetric.yaml").write_text(asymmetric)

    print(f"wrote incast and victim traces; victim terminals {s45}->{s44}; bottleneck={edge:.4f} Gbps")


if __name__ == "__main__":
    main()
