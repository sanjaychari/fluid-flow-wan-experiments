#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'common'))
from rate_fluid import load_summary

case = Path(sys.argv[1])
codes = {r['flow_id']: r for r in load_summary(case / 'rate-fluid-flow-summary.csv')}
sim = {int(r['flow_id']): r for r in csv.DictReader((case / 'simgrid-fct.csv').open())}

flow_ids = sorted(set(codes) | set(sim))
rows = []
for fid in flow_ids:
    if fid not in codes:
        raise RuntimeError(f'Flow {fid} missing from CODES results')
    if fid not in sim:
        raise RuntimeError(f'Flow {fid} missing from SimGrid results')

    cf = float(codes[fid]['fct_s'])
    sf = float(sim[fid]['fct_sec'])
    rows.append({
        'flow_id': fid,
        'codes_fct_s': cf,
        'simgrid_fct_s': sf,
        'abs_error_ms': 1000.0 * abs(cf - sf),
    })

out = ROOT / 'analysis/flow-comparison.csv'
out.parent.mkdir(exist_ok=True)
with out.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)

print(','.join(rows[0].keys()))
for r in rows:
    print(
        f"{r['flow_id']},{r['codes_fct_s']:.6f},"
        f"{r['simgrid_fct_s']:.6f},{r['abs_error_ms']:.6f}"
    )
