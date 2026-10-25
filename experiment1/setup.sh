#!/usr/bin/env bash
set -euo pipefail
E1="$(cd "$(dirname "$0")" && pwd)"
source "$E1/../common/env.sh"
require_executable "$RATE_BIN"

python3 - "$E1" <<'PY'
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).parent / 'common'))
from rate_fluid import DEFAULT_LINK_LATENCY_MS, write_config, write_flow_csv

root = Path(sys.argv[1])
inp = root / 'inputs'
inp.mkdir(parents=True, exist_ok=True)

# Mixed scientific-WAN workload: three persistent bulk transfers plus six
# shorter bursts. Every flow traverses the same 200-Gbps S0->S1 bottleneck,
# but terminates at a different destination terminal. All source-destination
# routes have the same three-link path length, so SimGrid's route-latency
# sharing penalty is identical across competing flows.
flows = [
    # start_s, flow_id, src, dst, size_gbit
    (0.0,  1001, 0,  6, 6000.0),
    (0.0,  1002, 1,  7, 4800.0),
    (5.0,  1003, 2,  8, 4000.0),
    (12.0, 2001, 3,  9,  200.0),
    (25.0, 2002, 4, 10,  300.0),
    (25.0, 2003, 5, 11,  160.0),
    (40.0, 2004, 3,  9,  250.0),
    (55.0, 2005, 4, 10,  160.0),
    (70.0, 2006, 5, 11,  250.0),
]

write_flow_csv(inp / 'flows.csv', flows)
write_config(
    inp / 'codes.yaml',
    switches=2,
    terminals=12,
    end_time_s=120.0,
    topology_file='topology.yaml',
    flow_file='flows.csv',
    latency_ms=DEFAULT_LINK_LATENCY_MS,
    pause_enabled=1,
    pause_hi=0.8,
    pause_lo=0.2,
    debug=1,
)

# Two-switch topology. T0-T5 attach to S0; T6-T11 attach to S1.
# The 200-Gbps inter-switch link is the shared bottleneck. Access links are
# also 200 Gbps, so no flow has an additional per-source/per-destination cap.
(inp / 'topology.yaml').write_text('''# Controlled mixed-transfer WAN topology.\n# All flows have equal three-link path length and share S0->S1.\n\ntopology:\n  switches:\n    S0:\n      terminals: 6\n      terminal_bandwidth: "200 Gbps"\n      switch_buffer: "2.0 GB"\n      connections:\n        S1: "200 Gbps"\n\n    S1:\n      terminals: 6\n      terminal_bandwidth: "200 Gbps"\n      switch_buffer: "2.0 GB"\n      connections:\n        S0: "200 Gbps"\n''')

# SimGrid traffic file uses 100-ms integer start intervals.
with (inp / 'traffic.csv').open('w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(['interval', 'flow_id', 'source_terminal', 'destination_terminal', 'offered_gbit'])
    for start, fid, src, dst, size in flows:
        interval = round(start / 0.1)
        if abs(interval * 0.1 - start) > 1e-9:
            raise RuntimeError(f'flow {fid} start {start} is not aligned to 100 ms')
        w.writerow([interval, fid, src, dst, f'{size:g}'])

# Directional access links prevent unrelated reverse traffic from sharing a
# SimGrid resource. Every active route contains exactly three 5-ms links:
# source-up, S0->S1, and destination-down.
lines = [
    "<?xml version='1.0'?>",
    '<!DOCTYPE platform SYSTEM "https://simgrid.org/simgrid.dtd">',
    '<platform version="4.1">',
    '  <zone id="AS0" routing="Full">',
]
for t in range(12):
    lines.append(f'    <host id="T{t}" speed="1Gf"/>')
for t in range(12):
    lines.append(f'    <link id="T{t}_up" bandwidth="25GBps" latency="0.005s"/>')
    lines.append(f'    <link id="T{t}_down" bandwidth="25GBps" latency="0.005s"/>')
lines.append('    <link id="S0_S1" bandwidth="25GBps" latency="0.005s"/>')
lines.append('    <link id="S1_S0" bandwidth="25GBps" latency="0.005s"/>')

for src, dst in sorted({(src, dst) for _start, _fid, src, dst, _size in flows}):
    lines.append(f'    <route src="T{src}" dst="T{dst}" symmetrical="NO">')
    lines.append(f'      <link_ctn id="T{src}_up"/>')
    lines.append('      <link_ctn id="S0_S1"/>')
    lines.append(f'      <link_ctn id="T{dst}_down"/>')
    lines.append('    </route>')

lines += ['  </zone>', '</platform>', '']
(inp / 'platform.xml').write_text('\n'.join(lines))
PY

mkdir -p "$E1/results" "$E1/analysis"
echo "Experiment 1 inputs ready: $RATE_BIN"
