#!/usr/bin/env python3
"""Small stdlib-only parser for generated Fluid-Flow WAN topology YAML.

It intentionally mirrors the CODES parser's switch-ID rule: IDs are assigned on
first mention, including connection targets that appear before their own block.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FluidTopology:
    switches: list[str]
    switch_index: dict[str, int]
    terminal_counts: list[int]
    terminal_bandwidth_mbps: list[float]
    switch_buffer_mbit: list[float]
    adjacency: list[list[int]]
    edge_mbps: dict[tuple[int, int], float]

    @property
    def terminal_to_switch(self) -> list[int]:
        out: list[int] = []
        for sid, count in enumerate(self.terminal_counts):
            out.extend([sid] * count)
        return out

    def terminals_on_switch(self, switch: str | int) -> list[int]:
        sid = self.switch_index[switch] if isinstance(switch, str) else int(switch)
        out: list[int] = []
        tid = 0
        for s, count in enumerate(self.terminal_counts):
            if s == sid:
                out.extend(range(tid, tid + count))
                break
            tid += count
        return out

    def bfs_path(self, src: int, dst: int) -> list[int]:
        if src == dst:
            return [src]
        prev = [-1] * len(self.switches)
        seen = [False] * len(self.switches)
        q = deque([src])
        seen[src] = True
        while q:
            u = q.popleft()
            for v in self.adjacency[u]:
                if not seen[v]:
                    seen[v] = True
                    prev[v] = u
                    q.append(v)
        if not seen[dst]:
            raise RuntimeError(f"no directed route {self.switches[src]} -> {self.switches[dst]}")
        path = [dst]
        cur = dst
        while cur != src:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path


def _quantity(raw: str, *, bandwidth: bool) -> float:
    raw = raw.strip().strip('"\'')
    units = "Mbps|Gbps" if bandwidth else "Mb|Gb"
    m = re.fullmatch(rf"([0-9.eE+-]+)\s*({units})", raw)
    if not m:
        raise ValueError(f"unsupported quantity: {raw}")
    value = float(m.group(1))
    return value * (1000.0 if m.group(2).startswith("G") else 1.0)


def parse_topology(path: str | Path) -> FluidTopology:
    path = Path(path)
    switches: list[str] = []
    index: dict[str, int] = {}
    counts: list[int] = []
    terminal_bw: list[float] = []
    buffers: list[float] = []
    adj: list[list[int]] = []
    edge_mbps: dict[tuple[int, int], float] = {}

    def get_or_add(name: str) -> int:
        if name in index:
            return index[name]
        sid = len(switches)
        index[name] = sid
        switches.append(name)
        counts.append(0)
        terminal_bw.append(0.0)
        buffers.append(0.0)
        adj.append([])
        return sid

    current: int | None = None
    in_connections = False
    for raw in path.read_text().splitlines():
        body = raw.split("#", 1)[0].rstrip()
        if not body.strip() or ":" not in body:
            continue
        indent = len(body) - len(body.lstrip(" "))
        key, value = [x.strip() for x in body.strip().split(":", 1)]

        if indent == 4 and value == "" and key != "switches":
            current = get_or_add(key)
            in_connections = False
            continue
        if current is None:
            continue
        if indent == 6 and key == "connections":
            in_connections = True
            continue
        if indent == 6 and not in_connections:
            if key == "terminals":
                counts[current] = int(value.strip('"\''))
            elif key == "terminal_bandwidth":
                terminal_bw[current] = _quantity(value, bandwidth=True)
            elif key == "switch_buffer":
                buffers[current] = _quantity(value, bandwidth=False)
            continue
        if indent == 8 and in_connections:
            dst = get_or_add(key)
            if dst not in adj[current]:
                adj[current].append(dst)
            edge_mbps[(current, dst)] = _quantity(value, bandwidth=True)

    # Intermediate routing switches are allowed to have zero attached
    # terminals (for example the StarLight router in Experiment 1).
    if not switches or any(c < 0 for c in counts) or sum(counts) <= 0:
        raise RuntimeError(f"could not parse complete topology from {path}")
    return FluidTopology(switches, index, counts, terminal_bw, buffers, adj, edge_mbps)
