# Experiment 1 — Mixed-transfer dynamic-sharing correctness

Validates `model-net-rate-fluid-wan` against SimGrid `raw` using a controlled
scientific-WAN workload with mixed persistent and burst transfers.

The workload combines three persistent bulk transfers with six shorter bursts.
Flows terminate at different destination terminals, but every source-destination
route has the same three-link path length: source access, the shared S0->S1 WAN
bottleneck, and destination access. Each link has 5-ms one-way latency, so all
flows have the same 15-ms propagation delay. Equal route length prevents
SimGrid's latency-dependent sharing penalty from favoring one competing flow.

The S0->S1 link is 200 Gbps and all access links are also 200 Gbps. Each
switch has a 2.0-GB shared buffer. Whole-link PAUSE is enabled with an 80% high
watermark and 20% low watermark, so transient bursts can exercise CODES's
explicit buffering and backpressure while SimGrid remains the analytical
flow-level reference. Experiment 2 separately stresses congestion and PAUSE
across a wider parameter sweep.

`analyze.py` compares destination-observed FCTs from CODES and SimGrid and
reports their absolute difference. Buffer occupancy and PAUSE behavior are
available in the CODES debug trace.

Run:

```bash
./experiment1/setup.sh
./experiment1/run.sh
```

Primary output:

```text
experiment1/analysis/flow-comparison.csv
```
