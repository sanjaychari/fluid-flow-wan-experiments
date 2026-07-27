#!/usr/bin/env python3
from __future__ import annotations
import csv,re,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cases={}
with (ROOT/"cases.csv").open(newline="") as f:
    for r in csv.DictReader(f): cases[r["point"]]=r
rows=[]
for point,case in cases.items():
    target=float(case["target_gbit"])
    for model in ("fluid","packet"):
        for log in sorted((ROOT/"results"/point/model).glob("repeat*/model-output.log")):
            rep=int(log.parent.name.replace("repeat","")); text=log.read_text(errors="replace")
            m=re.search(r"Running Time\s*[:=]\s*([0-9.eE+-]+)",text); e=re.search(r"Net Events Processed\s+([0-9]+)",text)
            if not m or not e: raise RuntimeError(f"missing runtime/events in {log}")
            runtime=float(m.group(1)); events=int(e.group(1))
            resource=(log.parent/"resource.txt").read_text(errors="replace") if (log.parent/"resource.txt").is_file() else ""
            rss=re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)",resource)
            rows.append({"point":point,"model":model,"repeat":rep,"hosts":int(case["hosts"]),"target_gbit":target,
                         "runtime_sec":runtime,"net_events":events,"net_event_rate_per_sec":events/runtime,
                         "events_per_simulated_gbit":events/target,"simulated_gbit_per_wall_sec":target/runtime,
                         "peak_rss_kb":int(rss.group(1)) if rss else 0})
out=ROOT/"analysis"/"experiment4-runs.csv"; out.parent.mkdir(parents=True,exist_ok=True)
with out.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows)
ag=[]
order={"small":0,"medium":1,"large":2}
for point in sorted(cases,key=order.get):
    for model in ("fluid","packet"):
        g=[r for r in rows if r["point"]==point and r["model"]==model]
        rec={"point":point,"model":model,"n":len(g),"hosts":g[0]["hosts"],"target_gbit":g[0]["target_gbit"]}
        for metric in ("runtime_sec","net_events","net_event_rate_per_sec","events_per_simulated_gbit","simulated_gbit_per_wall_sec","peak_rss_kb"):
            vals=[float(r[metric]) for r in g]; rec[f"{metric}_mean"]=statistics.mean(vals); rec[f"{metric}_std"]=statistics.stdev(vals) if len(vals)>1 else 0
        ag.append(rec)
agg=ROOT/"analysis"/"experiment4-summary.csv"
with agg.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(ag[0]),lineterminator="\n");w.writeheader();w.writerows(ag)
comp=[]
for point in sorted(cases,key=order.get):
    frow=next(r for r in ag if r["point"]==point and r["model"]=="fluid"); prow=next(r for r in ag if r["point"]==point and r["model"]=="packet")
    comp.append({"point":point,"target_gbit":frow["target_gbit"],
                 "fluid_runtime_mean_sec":frow["runtime_sec_mean"],"packet_runtime_mean_sec":prow["runtime_sec_mean"],
                 "fluid_gbit_per_wall_sec":frow["simulated_gbit_per_wall_sec_mean"],"packet_gbit_per_wall_sec":prow["simulated_gbit_per_wall_sec_mean"],
                 "fluid_events_per_gbit":frow["events_per_simulated_gbit_mean"],"packet_events_per_gbit":prow["events_per_simulated_gbit_mean"],
                 "data_rate_ratio_fluid_over_packet":frow["simulated_gbit_per_wall_sec_mean"]/prow["simulated_gbit_per_wall_sec_mean"],
                 "event_granularity_ratio_packet_over_fluid":prow["events_per_simulated_gbit_mean"]/frow["events_per_simulated_gbit_mean"]})
co=ROOT/"analysis"/"experiment4-comparison.csv"
with co.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(comp[0]),lineterminator="\n");w.writeheader();w.writerows(comp)
print(f"wrote {agg}"); print(f"wrote {co}")
