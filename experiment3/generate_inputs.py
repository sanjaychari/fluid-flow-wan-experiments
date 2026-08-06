#!/usr/bin/env python3
from __future__ import annotations
import csv
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
sys.path.insert(0,str(REPO/"common"))
from fluid_topology import parse_topology
CFG=ROOT/"configs"; TR=ROOT/"traces"
CFG.mkdir(parents=True,exist_ok=True); TR.mkdir(parents=True,exist_ok=True)
HOSTS=1056; PAYLOAD=262144
points=[("small",1),("medium",2),("large",4)]
packet_cfg=CFG/"packet-dragonfly-minimal.yaml"
packet_cfg.write_text('''schema_version: 1
components:
  compute_host:
    model: nw-lp

topology:
  format: parametric
  fabric:
    model: dragonfly
    shape:
      num_routers: 8
    links:
      local:  { bandwidth: 5.25, vc_size: 4096 }
      global: { bandwidth: 4.7,  vc_size: 8192 }
      cn:     { bandwidth: 5.25, vc_size: 4096 }
    routing:
      algorithm: minimal
    packet_size: 512
    chunk_size: 32
    num_vcs: 1
    modelnet_scheduler: fcfs
    message_size: 512
  hosts:
    component: compute_host
''')
# Map logical packet host IDs (router_id*4 + local_endpoint) to the terminal IDs
# assigned by the Fluid-Flow WAN parser.  Switch IDs are first-mention order, so
# fluid terminal IDs are deliberately not assumed to equal router_id*4+local.
topo=parse_topology(ROOT/"topologies"/"fluid-dragonfly.yaml")
logical_to_fluid={}
fluid_tid=0
for sid,count in enumerate(topo.terminal_counts):
    rid=int(topo.switches[sid][1:])
    for local in range(count):
        logical_to_fluid[rid*4+local]=fluid_tid
        fluid_tid += 1
if len(logical_to_fluid) != HOSTS:
    raise SystemExit(f"expected {HOSTS} logical hosts, got {len(logical_to_fluid)}")

rows=[]
for label,nmsg in points:
    target=HOSTS*nmsg*PAYLOAD*8/1e9
    trace=TR/f"fluid-{label}.csv"
    per=target/HOSTS
    with trace.open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["interval","flow_id","source_terminal","destination_terminal","offered_gbit"])
        for logical_src in range(HOSTS):
            logical_dst=(logical_src+32)%HOSTS
            src=logical_to_fluid[logical_src]
            dst=logical_to_fluid[logical_dst]
            w.writerow([0,40000+logical_src,src,dst,f"{per:.12f}"])
    cfg=CFG/f"fluid-{label}.yaml"
    cfg.write_text(f'''schema_version: 1

topology:
  format: groups
  params:
    message_size: 32768
    pe_mem_factor: 256
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        fluid-flow-wan-switch-lp: 264
        fluid-flow-wan-terminal-lp: 1056

sections:
  fluid_flow_wan:
    topology_yaml_file: "topology.yaml"
    traffic_trace_file: "traffic.csv"
    interval_seconds: 1
    num_send_intervals: 1
    num_drain_intervals: 30
    egress_model: pdes
    debug_prints: 0
    backpressure_delay_ms: 1.0
    pause_high_watermark_fraction: 0.80
    pause_low_watermark_fraction: 0.50
''')
    rows.append((label,nmsg,PAYLOAD,HOSTS,f"{target:.12f}",cfg.relative_to(ROOT),trace.relative_to(ROOT),packet_cfg.relative_to(ROOT)))
with (ROOT/"cases.csv").open("w",newline="") as f:
    w=csv.writer(f,lineterminator="\n")
    w.writerow(["point","packet_num_messages","packet_payload_bytes","hosts","target_gbit","fluid_config","fluid_trace","packet_config"])
    w.writerows(rows)
print(f"wrote {len(rows)} matched Experiment 3 points")
