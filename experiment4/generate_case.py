#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,random,sys
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'common'))
from fluid_topology import parse_topology
from rate_fluid import DEFAULT_LINK_LATENCY_MS, write_config,write_flow_csv

SWITCHES=128
BASE_START_SPAN_S=60.0
BASE_SIZE_GB=(5.0,20.0)
FLOW_COUNTS={'very_sparse':8,'sparse':32,'medium':128,'dense':256}
WORKLOAD_SEED=44004


def write_topology(path:Path,n:int=SWITCHES,seed=12345):
    rng=random.Random(seed+n); edges={i:{(i-1)%n,(i+1)%n} for i in range(n)}
    while sum(map(len,edges.values())) < 3*n:
        a=rng.randrange(n); b=rng.randrange(n)
        if a!=b: edges[a].add(b)
    lines=['topology:','  switches:']
    for s in range(n):
        lines += [f'    S{s}:','      terminals: 2','      terminal_bandwidth: "100 Gbps"','      switch_buffer: "125 GB"','      connections:']
        for d in sorted(edges[s]): lines.append(f'        S{d}: "{rng.uniform(10,30):.4f} Gbps"')
    path.write_text('\n'.join(lines)+'\n')


def bfs(adj,s,d):
    q=deque([s]); prev={s:None}
    while q:
        u=q.popleft()
        if u==d: break
        for v in adj[u]:
            if v not in prev: prev[v]=u; q.append(v)
    if d not in prev: raise RuntimeError(f'no route {s}->{d}')
    out=[]; u=d
    while u is not None: out.append(u); u=prev[u]
    return out[::-1]


def write_platform(path:Path,topology_path:Path,flows,lat_ms:float):
    topo=parse_topology(topology_path); t2s=topo.terminal_to_switch
    lines=["<?xml version='1.0'?>",'<!DOCTYPE platform SYSTEM "https://simgrid.org/simgrid.dtd">','<platform version="4.1">','  <zone id="AS0" routing="Full">']
    for t in range(len(t2s)): lines.append(f'    <host id="T{t}" speed="1Gf"/>')
    for t,sid in enumerate(t2s):
        gbps=topo.terminal_bandwidth_mbps[sid]/1000.0
        lines.append(f'    <link id="T{t}_up" bandwidth="{gbps/8:g}GBps" latency="{lat_ms/1000:g}s"/>')
        lines.append(f'    <link id="T{t}_down" bandwidth="{gbps/8:g}GBps" latency="{lat_ms/1000:g}s"/>')
    for (a,b),mbps in sorted(topo.edge_mbps.items()):
        lines.append(f'    <link id="S{a}_S{b}" bandwidth="{mbps/8000:g}GBps" latency="{lat_ms/1000:g}s"/>')
    seen=set()
    for _,_,src,dst,_ in flows:
        if (src,dst) in seen: continue
        seen.add((src,dst))
        path_sw=bfs(topo.adjacency,t2s[src],t2s[dst])
        lines.append(f'    <route src="T{src}" dst="T{dst}" symmetrical="NO">'); lines.append(f'      <link_ctn id="T{src}_up"/>')
        for a,b in zip(path_sw,path_sw[1:]): lines.append(f'      <link_ctn id="S{a}_S{b}"/>')
        lines.append(f'      <link_ctn id="T{dst}_down"/>'); lines.append('    </route>')
    lines += ['  </zone>','</platform>','']; path.write_text('\n'.join(lines))


def dense_workload(nt:int):
    rng=random.Random(WORKLOAD_SEED)
    flows=[]
    for i in range(nt):
        src=i
        dst=(i+nt//2)%nt
        start=rng.random()*BASE_START_SPAN_S
        size_gbit=rng.uniform(*BASE_SIZE_GB)*8.0
        flows.append((start,i+1,src,dst,size_gbit))
    flows.sort(key=lambda x:(x[0],x[1]))
    return flows


def evenly_spaced_subset(items,n:int):
    if n == len(items):
        return list(items)
    if n < 1 or n > len(items):
        raise ValueError(f'invalid subset size {n} for {len(items)} items')
    idx=[round(i*(len(items)-1)/(n-1)) for i in range(n)] if n > 1 else [0]
    return [items[i] for i in idx]


def build_flows(nt:int,density:str):
    dense=dense_workload(nt)
    target_n=FLOW_COUNTS[density]
    selected=evenly_spaced_subset(dense,target_n)
    dense_total=sum(x[4] for x in dense)
    selected_total=sum(x[4] for x in selected)
    size_scale=dense_total/selected_total
    flows=[(st,fid,src,dst,gbit*size_scale) for st,fid,src,dst,gbit in selected]
    return flows,size_scale,dense_total


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--case-dir',type=Path,required=True)
    ap.add_argument('--density',choices=tuple(FLOW_COUNTS),required=True)
    ap.add_argument('--link-latency-ms',type=float,default=DEFAULT_LINK_LATENCY_MS)
    a=ap.parse_args()

    c=a.case_dir; c.mkdir(parents=True,exist_ok=True)
    write_topology(c/'topology.yaml')
    topo=parse_topology(c/'topology.yaml'); nt=len(topo.terminal_to_switch)
    flows,size_scale,dense_total=build_flows(nt,a.density)
    write_flow_csv(c/'flows.csv',flows)

    min_edge_gbps=min(topo.edge_mbps.values())/1000.0
    max_start=max(x[0] for x in flows)
    total_gbit=sum(x[4] for x in flows)
    end_time_s=max_start + total_gbit/min_edge_gbps + 60.0
    write_config(c/'codes.yaml',switches=SWITCHES,terminals=nt,end_time_s=end_time_s,
                 latency_ms=a.link_latency_ms,pause_enabled=0,debug=0)

    with (c/'traffic.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['start_time_sec','flow_id','source_terminal','destination_terminal','offered_gbit'])
        for st,fid,s,d,z in flows: w.writerow([f'{st:.12g}',fid,s,d,f'{z:.12g}'])

    with (c/'workload-metadata.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['flow_density','switches','flows','start_span_s','offered_GB','size_scale_vs_selected_subset'])
        starts=[x[0] for x in flows]
        w.writerow([a.density,SWITCHES,len(flows),f'{max(starts)-min(starts):.9f}',f'{total_gbit/8.0:.9f}',f'{size_scale:.9f}'])

    if abs(total_gbit-dense_total) > 1e-6:
        raise RuntimeError(f'offered-volume mismatch for {a.density}: {total_gbit} vs {dense_total}')

    write_platform(c/'platform.xml',c/'topology.yaml',flows,a.link_latency_ms)
    print(f'density={a.density} switches={SWITCHES} flows={len(flows)} '
          f'start_span_s={max(starts)-min(starts):.6f} offered_GB={total_gbit/8.0:.6f} '
          f'size_scale={size_scale:.6f}')


if __name__=='__main__':main()
