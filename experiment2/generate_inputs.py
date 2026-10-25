#!/usr/bin/env python3
from __future__ import annotations
import csv,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT.parent/'common'))
from rate_fluid import write_config, write_flow_csv
from fluid_topology import parse_topology
CFG=ROOT/'configs'; TR=ROOT/'traces'; CFG.mkdir(exist_ok=True); TR.mkdir(exist_ok=True)
SEEDS=range(2001,2011)

base=parse_topology(ROOT/'topologies/topology-buffer100Gb.yaml'); N=len(base.terminal_to_switch)

def ensure_buffer_topology(buffer_gb:int):
    src=ROOT/'topologies/topology-buffer100Gb.yaml'
    dst=ROOT/f'topologies/topology-buffer{buffer_gb}Gb.yaml'
    text=src.read_text().replace('switch_buffer: \"100 Gb\"', f'switch_buffer: \"{buffer_gb} Gb\"')
    dst.write_text(text)
    return dst

def random_flows(seed:int,count:int,size_lo:float,size_hi:float,horizon:float=100):
    rng=random.Random(seed); rows=[]
    for i in range(count):
        src=rng.randrange(N); dst=rng.randrange(N-1); dst += dst>=src
        rows.append((rng.random()*horizon, seed*10000+i, src,dst,rng.uniform(size_lo,size_hi)))
    return rows

def emit(name,scenario,seed,topology,rows,hi=.80,lo=.50,end=400):
    flow=TR/f'{name}.csv'; write_flow_csv(flow,rows)
    cfg=CFG/f'{name}.yaml'; write_config(cfg,switches=64,terminals=128,end_time_s=end,topology_file='topology.yaml',flow_file='flows.csv',latency_ms=5,pause_enabled=1,pause_hi=hi,pause_lo=lo,debug=1)
    cases.append((name,scenario,seed,cfg.relative_to(ROOT),Path(topology).relative_to(ROOT),flow.relative_to(ROOT)))

cases=[]
# A: increasing offered concurrency/volume on the same topology.
for level,count in [('low',64),('medium',128),('high',256)]:
 for seed in SEEDS: emit(f'load-{level}-seed{seed}','A-load',seed,ROOT/'topologies/topology-buffer100Gb.yaml',random_flows(seed,count,25,100))
# B: paired high-load traces across buffer sizes and PAUSE thresholds.
policies={'aggressive':(.50,.30),'moderate':(.80,.50)}
for b in (5,10,20):
 topology=ensure_buffer_topology(b)
 for policy,(hi,lo) in policies.items():
  for seed in SEEDS: emit(f'buffer{b}Gb-{policy}-seed{seed}','B-buffer-pause',seed,topology,random_flows(seed,256,25,100),hi,lo)
# C: synchronized finite incast; paired source sets across fan-in.
for fanin in (4,8,16):
 for seed in SEEDS:
  rng=random.Random(seed*100+fanin); dst=0; srcs=rng.sample(list(range(1,N)),fanin)
  emit(f'incast-{fanin}-seed{seed}','C-incast',seed,ROOT/'topologies/topology-buffer100Gb.yaml',[(0,500000+seed*100+i,s,dst,100) for i,s in enumerate(srcs)],end=200)
# D: same finite elephant/victim workload on the asymmetric/symmetric paired topologies.
for mode in ('asymmetric','symmetric'):
 topo=parse_topology(ROOT/f'topologies/topology-victim-{mode}.yaml'); s44=topo.terminals_on_switch('S44')[0]; s45=topo.terminals_on_switch('S45')[0]
 rows=[(0,70000+i,s44,s45,3000) for i in range(8)]+[(0,70008,s44,s45,400)]
 emit(f'victim-{mode}','D-victim',0,ROOT/f'topologies/topology-victim-{mode}.yaml',rows,end=2000)
with (ROOT/'cases.csv').open('w',newline='') as f:
 w=csv.writer(f,lineterminator='\n'); w.writerow(['case','scenario','seed','config','topology','flow_file']); w.writerows(cases)
print(f'wrote {len(cases)} Experiment 2 cases')
