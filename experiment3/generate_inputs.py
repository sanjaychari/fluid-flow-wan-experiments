#!/usr/bin/env python3
from __future__ import annotations
import csv,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent; REPO=ROOT.parent; sys.path.insert(0,str(REPO/'common'))
from fluid_topology import parse_topology
from rate_fluid import write_config, write_flow_csv
CFG=ROOT/'configs'; TR=ROOT/'traces'; CFG.mkdir(parents=True,exist_ok=True); TR.mkdir(parents=True,exist_ok=True)
HOSTS=1056; PAYLOAD=262144; points=[('small',1),('medium',2),('large',4)]
packet_cfg=CFG/'packet-dragonfly-minimal.yaml'
packet_cfg.write_text('''schema_version: 1
components:
  compute_host:
    model: nw-lp
topology:
  format: parametric
  fabric:
    model: dragonfly
    shape: { num_routers: 8 }
    links:
      local:  { bandwidth: 5.25, vc_size: 4096 }
      global: { bandwidth: 4.7,  vc_size: 8192 }
      cn:     { bandwidth: 5.25, vc_size: 4096 }
    routing: { algorithm: minimal }
    packet_size: 512
    chunk_size: 32
    num_vcs: 1
    modelnet_scheduler: fcfs
    message_size: 512
  hosts: { component: compute_host }
''')
topo=parse_topology(ROOT/'topologies/fluid-dragonfly.yaml'); logical_to_fluid={}; fluid_tid=0
for sid,count in enumerate(topo.terminal_counts):
 rid=int(topo.switches[sid][1:])
 for local in range(count): logical_to_fluid[rid*4+local]=fluid_tid; fluid_tid+=1
rows=[]
for label,nmsg in points:
 target=HOSTS*nmsg*PAYLOAD*8/1e9; per=target/HOSTS; flow=TR/f'fluid-{label}.csv'
 specs=[]
 for logical_src in range(HOSTS):
  logical_dst=(logical_src+32)%HOSTS; specs.append((0,40000+logical_src,logical_to_fluid[logical_src],logical_to_fluid[logical_dst],per))
 write_flow_csv(flow,specs)
 cfg=CFG/f'fluid-{label}.yaml'; write_config(cfg,switches=264,terminals=1056,end_time_s=30,topology_file='topology.yaml',flow_file='flows.csv',latency_ms=5,pause_enabled=1,debug=0,pe_mem_factor=256)
 rows.append((label,nmsg,PAYLOAD,HOSTS,f'{target:.12f}',cfg.relative_to(ROOT),flow.relative_to(ROOT),packet_cfg.relative_to(ROOT)))
with (ROOT/'cases.csv').open('w',newline='') as f:
 w=csv.writer(f,lineterminator='\n'); w.writerow(['point','packet_num_messages','packet_payload_bytes','hosts','target_gbit','fluid_config','fluid_trace','packet_config']); w.writerows(rows)
