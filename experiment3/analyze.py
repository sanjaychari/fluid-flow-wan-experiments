#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def pct(values, q):
    if not values: return 0.0
    v=sorted(values)
    if len(v)==1: return v[0]
    x=(len(v)-1)*q; lo=math.floor(x); hi=math.ceil(x)
    return v[lo] if lo==hi else v[lo]*(hi-x)+v[hi]*(x-lo)


def parse_one(log: Path, switches: int, load: str, mode: str, repeat: int):
    text=log.read_text(errors="replace")
    rt=re.search(r"Running Time\s*[:=]\s*([0-9.eE+-]+)",text)
    events=re.search(r"Net Events Processed\s+([0-9]+)",text)
    generated=sum(float(x) for x in re.findall(r"fluid-flow-wan-terminal .*? generated_gbit=([0-9.eE+-]+)",text))
    if not generated:
        generated=sum(float(x)/1000.0 for x in re.findall(r"fluid-flow-wan-terminal .*? generated_mbit=([0-9.eE+-]+)",text))
    runtime=float(rt.group(1)) if rt else 0.0
    row={
        "switches":switches,"terminals":switches*2,"load":load,"mode":mode,"repeat":repeat,
        "runtime_sec":runtime,"net_events":int(events.group(1)) if events else 0,
        "generated_gbit":generated,"simulated_gbit_per_wall_sec":generated/runtime if runtime else 0.0,
        "zmq_requests":0,"zmq_processing_mean_sec":0.0,"zmq_total_mean_sec":0.0,
        "zmq_client_transport_mean_sec":0.0,"zmq_accumulated_total_sec":0.0,
        "zmq_batch_requests":0,"zmq_query_rows":0,"zmq_cache_hits":0,"zmq_mean_batch_size":0.0,
    }
    stats={}
    pat=re.compile(r"==DIR_STATS (zmq-processing-global|zmq-total-global): requests = (\d+), mean = ([0-9.eE+-]+), min = ([0-9.eE+-]+), max = ([0-9.eE+-]+), std-deviation = ([0-9.eE+-]+)")
    for m in pat.finditer(text): stats[m.group(1)]=m
    if "zmq-total-global" in stats:
        m=stats["zmq-total-global"]; row["zmq_requests"]=int(m.group(2)); row["zmq_total_mean_sec"]=float(m.group(3))
    if "zmq-processing-global" in stats:
        m=stats["zmq-processing-global"]; row["zmq_processing_mean_sec"]=float(m.group(3))
    row["zmq_client_transport_mean_sec"]=max(0.0,row["zmq_total_mean_sec"]-row["zmq_processing_mean_sec"])
    row["zmq_accumulated_total_sec"]=row["zmq_requests"]*row["zmq_total_mean_sec"]

    # Optional automatic-batching fields in newer model builds.
    batches=[]
    for m in re.finditer(r"fluid-flow-wan gid=.*? zmq_batch_requests=(\d+) zmq_query_rows=(\d+) zmq_cache_hits=(\d+) zmq_mean_batch_size=([0-9.eE+-]+)",text):
        batches.append(tuple(map(float,m.groups())))
    if batches:
        row["zmq_batch_requests"]=int(sum(x[0] for x in batches))
        row["zmq_query_rows"]=int(sum(x[1] for x in batches))
        row["zmq_cache_hits"]=int(sum(x[2] for x in batches))
        row["zmq_mean_batch_size"]=row["zmq_query_rows"]/row["zmq_batch_requests"] if row["zmq_batch_requests"] else 0.0
    return row


def main():
    rows=[]
    for log in ROOT.glob("results/scale*/*/*/repeat*/model-output.log"):
        scale=int(log.parts[-5].replace("scale","")); load=log.parts[-4]; mode=log.parts[-3]
        repeat=int(log.parts[-2].replace("repeat",""))
        rows.append(parse_one(log,scale,load,mode,repeat))
    rows.sort(key=lambda r:(r["switches"],r["load"],r["mode"],r["repeat"]))
    if not rows: raise SystemExit("no measured Experiment 3 outputs found")
    out=ROOT/"analysis"/"experiment3-runs.csv"; out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)

    aggs=[]
    keys=sorted({(r["switches"],r["load"],r["mode"]) for r in rows})
    for sw,load,mode in keys:
        g=[r for r in rows if (r["switches"],r["load"],r["mode"])==(sw,load,mode)]
        rec={"switches":sw,"terminals":sw*2,"load":load,"mode":mode,"n":len(g)}
        for metric in ("runtime_sec","simulated_gbit_per_wall_sec","zmq_requests","zmq_processing_mean_sec","zmq_total_mean_sec","zmq_client_transport_mean_sec","zmq_accumulated_total_sec","zmq_batch_requests","zmq_query_rows","zmq_cache_hits","zmq_mean_batch_size"):
            vals=[float(r[metric]) for r in g]
            rec[f"{metric}_mean"]=statistics.mean(vals)
            rec[f"{metric}_std"]=statistics.stdev(vals) if len(vals)>1 else 0.0
        aggs.append(rec)
    agg=ROOT/"analysis"/"experiment3-summary.csv"
    with agg.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(aggs[0]),lineterminator="\n");w.writeheader();w.writerows(aggs)

    pairs=[]
    for sw,load in sorted({(r["switches"],r["load"]) for r in rows}):
        p=[r for r in rows if r["switches"]==sw and r["load"]==load and r["mode"]=="pdes"]
        s=[r for r in rows if r["switches"]==sw and r["load"]==load and r["mode"]=="statistical"]
        if not p or not s: continue
        pr=statistics.mean(x["runtime_sec"] for x in p); sr=statistics.mean(x["runtime_sec"] for x in s)
        pg=statistics.mean(x["simulated_gbit_per_wall_sec"] for x in p); sg=statistics.mean(x["simulated_gbit_per_wall_sec"] for x in s)
        req=statistics.mean(x["zmq_requests"] for x in s)
        qtime=statistics.mean(x["zmq_accumulated_total_sec"] for x in s)
        pairs.append({"switches":sw,"terminals":sw*2,"load":load,"pdes_runtime_mean_sec":pr,
                      "statistical_runtime_mean_sec":sr,"runtime_overhead_sec":sr-pr,"runtime_ratio":sr/pr if pr else 0,
                      "pdes_simulated_gbit_per_wall_sec":pg,"statistical_simulated_gbit_per_wall_sec":sg,
                      "physical_zmq_requests_mean":req,"accumulated_zmq_total_sec_mean":qtime,
                      "query_wait_fraction_of_runtime_overhead":qtime/(sr-pr) if sr>pr else 0})
    pairout=ROOT/"analysis"/"experiment3-paired.csv"
    with pairout.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(pairs[0]),lineterminator="\n");w.writeheader();w.writerows(pairs)

    diagnostics=[]
    latpat=re.compile(r"\[fluid-flow-wan zmq latency\].*?processing_sec=([0-9.eE+-]+) total_sec=([0-9.eE+-]+) client_transport_sec=([0-9.eE+-]+)")
    for log in ROOT.glob("results/scale*/*/statistical/diagnostic/model-output.log"):
        sw=int(log.parts[-5].replace("scale","")); load=log.parts[-4]
        samples=[tuple(map(float,m.groups())) for m in latpat.finditer(log.read_text(errors="replace"))]
        if not samples: continue
        for idx,name in enumerate(("processing","total","client_transport")):
            vals=[x[idx] for x in samples]
            diagnostics.append({"switches":sw,"load":load,"metric":name,"samples":len(vals),
                                "mean_sec":statistics.mean(vals),"p50_sec":pct(vals,.50),"p95_sec":pct(vals,.95),"p99_sec":pct(vals,.99),"max_sec":max(vals)})
    if diagnostics:
        d=ROOT/"analysis"/"experiment3-diagnostic-latency.csv"
        with d.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(diagnostics[0]),lineterminator="\n");w.writeheader();w.writerows(diagnostics)
    print(f"wrote {agg}")
    print(f"wrote {pairout}")

if __name__=="__main__": main()
