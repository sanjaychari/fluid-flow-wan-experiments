#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from collections import deque
from pathlib import Path
from xml.sax.saxutils import escape


def parse_quantity_mbps(raw: str) -> float:
    raw = raw.strip().strip('"\'')
    m = re.fullmatch(r"([0-9.eE+-]+)\s*(Mbps|Gbps)", raw)
    if not m:
        raise ValueError(f"unsupported bandwidth: {raw}")
    value = float(m.group(1))
    return value * (1000.0 if m.group(2) == "Gbps" else 1.0)


def parse_topology(path: Path):
    # Match model-net-fluid-flow-wan.cxx exactly: a switch ID is assigned on
    # first mention, including when it first appears as a connection target.
    switches = []
    sw_index = {}
    terminal_counts = []
    terminal_bw_mbps = []
    adj = []
    edge_bw = {}

    def get_or_add(name: str) -> int:
        if name in sw_index:
            return sw_index[name]
        idx = len(switches)
        sw_index[name] = idx
        switches.append(name)
        terminal_counts.append(0)
        terminal_bw_mbps.append(0.0)
        adj.append([])
        return idx

    current = None
    in_connections = False
    for raw in path.read_text().splitlines():
        line_no_comment = raw.split('#', 1)[0].rstrip()
        if not line_no_comment.strip():
            continue
        indent = len(line_no_comment) - len(line_no_comment.lstrip(' '))
        line = line_no_comment.strip()
        if ':' not in line:
            continue
        key, value = [x.strip() for x in line.split(':', 1)]

        if indent == 4 and value == '' and key != 'switches':
            current = get_or_add(key)
            in_connections = False
            continue

        if current is None:
            continue
        if indent == 6 and key == 'connections':
            in_connections = True
            continue
        if indent == 6 and not in_connections:
            if key == 'terminals':
                terminal_counts[current] = int(value.strip('"\''))
            elif key == 'terminal_bandwidth':
                terminal_bw_mbps[current] = parse_quantity_mbps(value)
            continue
        if indent == 8 and in_connections:
            dst = get_or_add(key)
            # add_or_update_link() preserves the first insertion position.
            if dst not in adj[current]:
                adj[current].append(dst)
            edge_bw[(switches[current], switches[dst])] = parse_quantity_mbps(value)

    if not switches:
        raise RuntimeError(f"no switches parsed from {path}")
    if any(c <= 0 for c in terminal_counts):
        raise RuntimeError(f"one or more switches have no terminal count in {path}")
    return switches, terminal_counts, terminal_bw_mbps, adj, edge_bw

def bfs_path(adj, src: int, dst: int):
    if src == dst:
        return [src]
    prev = [-1] * len(adj)
    seen = [False] * len(adj)
    q = deque([src])
    seen[src] = True
    while q:
        u = q.popleft()
        for v in adj[u]:
            if not seen[v]:
                seen[v] = True
                prev[v] = u
                q.append(v)
    if not seen[dst]:
        raise RuntimeError(f"no route {src}->{dst}")
    out = [dst]
    cur = dst
    while cur != src:
        cur = prev[cur]
        out.append(cur)
    out.reverse()
    return out


def write_traffic(path: Path, terminals: int, flow_gbit: float):
    with path.open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['interval', 'flow_id', 'source_terminal', 'destination_terminal', 'offered_gbit'])
        shift = terminals // 2
        for src in range(terminals):
            dst = (src + shift) % terminals
            w.writerow([0, src + 1, src, dst, f"{flow_gbit:.9f}"])


def write_platform(path: Path, topology_path: Path, traffic_path: Path):
    switches, terminal_counts, terminal_bw, adj, edge_bw = parse_topology(topology_path)

    terminal_to_switch = []
    terminal_bws = []
    for s, count in enumerate(terminal_counts):
        for _ in range(count):
            terminal_to_switch.append(s)
            terminal_bws.append(terminal_bw[s])

    flows = []
    with traffic_path.open(newline='') as f:
        for row in csv.DictReader(f):
            flows.append((int(row['source_terminal']), int(row['destination_terminal'])))

    lines = [
        "<?xml version='1.0'?>",
        '<!DOCTYPE platform SYSTEM "https://simgrid.org/simgrid.dtd">',
        '<platform version="4.1">',
        '  <zone id="AS0" routing="Full">',
    ]
    for t in range(len(terminal_to_switch)):
        lines.append(f'    <host id="T{t}" speed="1Gf"/>')

    # Separate directional terminal links match the source and destination access capacities.
    for t, bw_mbps in enumerate(terminal_bws):
        mbps_bytes = bw_mbps / 8.0
        lines.append(f'    <link id="T{t}_up" bandwidth="{mbps_bytes:.9f}MBps" latency="0s"/>')
        lines.append(f'    <link id="T{t}_down" bandwidth="{mbps_bytes:.9f}MBps" latency="1s"/>')

    for s, nbrs in enumerate(adj):
        for d in nbrs:
            bw_mbps = edge_bw[(switches[s], switches[d])]
            mbps_bytes = bw_mbps / 8.0
            # CODES forwards a switch-egress fragment to the next hop in the next interval.
            lines.append(
                f'    <link id="S{s}_S{d}" bandwidth="{mbps_bytes:.9f}MBps" latency="1s"/>'
            )

    seen_pairs = set()
    for src_t, dst_t in flows:
        pair = (src_t, dst_t)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        src_s = terminal_to_switch[src_t]
        dst_s = terminal_to_switch[dst_t]
        path_sw = bfs_path(adj, src_s, dst_s)
        lines.append(f'    <route src="T{src_t}" dst="T{dst_t}" symmetrical="NO">')
        lines.append(f'      <link_ctn id="T{src_t}_up"/>')
        for a, b in zip(path_sw, path_sw[1:]):
            lines.append(f'      <link_ctn id="S{a}_S{b}"/>')
        lines.append(f'      <link_ctn id="T{dst_t}_down"/>')
        lines.append('    </route>')

    lines += ['  </zone>', '</platform>', '']
    path.write_text('\n'.join(lines))


def write_codes_config(path: Path, topology: Path, traffic: Path, switches: int, terminals: int,
                       drain_intervals: int, terminal_log: Path | None):
    log_line = f'    terminal_log_path: "{terminal_log.name}"\n' if terminal_log else ''
    path.write_text(f'''schema_version: 1

topology:
  format: groups
  params:
    message_size: 32768
    pe_mem_factor: 1024
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        fluid-flow-wan-switch-lp: {switches}
        fluid-flow-wan-terminal-lp: {terminals}

sections:
  fluid_flow_wan:
    topology_yaml_file: "{topology.name}"
    traffic_trace_file: "{traffic.name}"
    interval_seconds: 1
    num_send_intervals: 1
    num_drain_intervals: {drain_intervals}
    egress_model: pdes
    debug_prints: 0
    backpressure_delay_ms: 1.0
    pause_high_watermark_fraction: 0.999999
    pause_low_watermark_fraction: 0.999998
{log_line}''')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--codes-root', type=Path, required=True)
    ap.add_argument('--case-dir', type=Path, required=True)
    ap.add_argument('--switches', type=int, required=True, choices=(32, 64, 128))
    ap.add_argument('--flow-gbit', type=float, default=500.0)
    ap.add_argument('--pilot-drain', type=int, default=1000)
    ap.add_argument('--performance-drain', type=int)
    args = ap.parse_args()

    case = args.case_dir.resolve()
    case.mkdir(parents=True, exist_ok=True)
    topology = case / 'topology.yaml'
    traffic = case / 'traffic.csv'

    if args.performance_drain is None:
        generator = args.codes_root / 'src/network-workloads/generate-fluid-flow-wan-topology.py'
        subprocess.run([
            'python3', str(generator),
            '--switches', str(args.switches),
            '--terminals-per-switch', '2',
            '--avg-switch-degree', '3',
            '--reverse-link-probability', '0.35',
            '--switch-link-min-mbps', '10000',
            '--switch-link-max-mbps', '30000',
            '--terminal-link-min-mbps', '100000',
            '--terminal-link-max-mbps', '100000',
            '--switch-buffer-min-mb', '1000000000',
            '--switch-buffer-max-mb', '1000000000',
            '--seed', '12345',
            '--output', str(topology),
        ], check=True)
        terminals = args.switches * 2
        write_traffic(traffic, terminals, args.flow_gbit)
        write_platform(case / 'platform.xml', topology, traffic)
        write_codes_config(
            case / 'codes-correctness.yaml', topology, traffic,
            args.switches, terminals, args.pilot_drain,
            case / 'terminal-events.csv'
        )
    else:
        terminals = args.switches * 2
        if not topology.exists() or not traffic.exists():
            raise SystemExit('generate the case before creating the performance config')
        write_codes_config(
            case / 'codes-performance.yaml', topology, traffic,
            args.switches, terminals, args.performance_drain, None
        )


if __name__ == '__main__':
    main()
