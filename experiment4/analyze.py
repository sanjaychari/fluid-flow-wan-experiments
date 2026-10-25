#!/usr/bin/env python3
from __future__ import annotations
import csv,re,statistics,sys
from collections import defaultdict
from pathlib import Path

r=Path(sys.argv[1])
groups=defaultdict(list)
for x in csv.DictReader((r/'runtime.csv').open()):
    groups[(x['flow_density'],x['model'])].append(float(x['runtime_sec']))

order={'very_sparse':0,'sparse':1,'medium':2,'dense':3}
rows=[]
for density in sorted({k[0] for k in groups},key=lambda x:order[x]):
    case=r/density
    meta=next(csv.DictReader((case/'workload-metadata.csv').open()))
    codes=groups[(density,'codes')]; simgrid=groups[(density,'simgrid')]
    events=[]
    for i in range(1,len(codes)+1):
        text=(case/f'codes-{i}.out').read_text(errors='replace')
        m=re.search(r'Net Events Processed\s+([0-9]+)',text)
        if not m:
            raise RuntimeError(f'missing ROSS event count in {case/f"codes-{i}.out"}')
        events.append(int(m.group(1)))
    cm=statistics.mean(codes); sm=statistics.mean(simgrid)
    rows.append({
        'flow_density':density,
        'switches':int(meta['switches']),
        'flows':int(meta['flows']),
        'start_span_s':float(meta['start_span_s']),
        'offered_GB':float(meta['offered_GB']),
        'codes_runtime_sec_mean':cm,
        'codes_runtime_sec_std':statistics.stdev(codes) if len(codes)>1 else 0.0,
        'simgrid_runtime_sec_mean':sm,
        'simgrid_runtime_sec_std':statistics.stdev(simgrid) if len(simgrid)>1 else 0.0,
        'codes_over_simgrid_runtime_ratio':cm/sm,
        'codes_net_events_mean':statistics.mean(events),
        'codes_events_per_flow':statistics.mean(events)/int(meta['flows']),
    })

out=r/'experiment4-flow-density-summary.csv'
with out.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n'); w.writeheader(); w.writerows(rows)
print(out)
print(','.join(rows[0].keys()))
for row in rows:
    print(','.join(str(row[k]) for k in rows[0]))
