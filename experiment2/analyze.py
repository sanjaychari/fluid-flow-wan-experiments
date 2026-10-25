#!/usr/bin/env python3
from __future__ import annotations
import csv,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT.parent/'common'))
from rate_fluid import load_summary
rows=[]
with (ROOT/'cases.csv').open(newline='') as f: cases=list(csv.DictReader(f))
for c in cases:
 d=ROOT/'results'/c['case']/'sync1'; sp=d/'rate-fluid-flow-summary.csv'; log=d/'codes.out'
 if not sp.exists(): continue
 s=load_summary(sp); text=log.read_text(errors='replace')
 finals=[(float(a),float(b)) for a,b in re.findall(r'FINAL switch \S+ max_buffer=([0-9.eE+-]+) \S+ dropped=([0-9.eE+-]+)',text)]
 rows.append({'case':c['case'],'scenario':c['scenario'],'seed':c['seed'],'flows':len(s),'completed':sum(x['completed'] for x in s),'completion_fraction':sum(x['completed'] for x in s)/len(s),'mean_fct_s':sum(x['fct_s'] for x in s if x['completed'])/max(1,sum(x['completed'] for x in s)),'max_switch_buffer':max((x[0] for x in finals),default=0),'total_dropped':sum(x[1] for x in finals),'pause_updates':len(re.findall(r'PAUSE UPDATE\(',text))})
out=ROOT/'analysis/experiment2-summary.csv'; out.parent.mkdir(exist_ok=True)
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
print(f'wrote {out} ({len(rows)} cases)')
