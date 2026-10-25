# Experiment 4 — CODES versus SimGrid across flow density

Experiment 4 fixes the network at 128 switches (two terminals per switch), the
physical link latency at 5 ms per hop, the workload start window at about 60 s,
and the total offered data volume. It then compares `model-net-rate-fluid-wan`
against SimGrid raw while varying how that fixed volume is represented as flows.

The dense 256-flow workload is generated first. The medium and sparse cases use
evenly distributed subsets of the same deterministic workload so that their
start times still span the same observation window. Selected flow sizes are then
rescaled so all three cases carry exactly the same aggregate offered volume:

- **sparse:** 32 large flows;
- **medium:** 128 medium flows;
- **dense:** 256 baseline flows.

This isolates a principal cost driver of the rate-based CODES model: the number
of persistent flows and the resulting flow registration, rate-allocation,
feedback, and completion events. The topology, total represented data, arrival
window, routing rules, link capacities, and per-hop latency remain fixed.

The main output is `results/experiment4-flow-density-summary.csv`, which reports
mean simulation runtime for CODES and SimGrid, the CODES/SimGrid runtime ratio,
flow count, offered volume, start-time span, mean ROSS event count, and events
per flow.

Run:

```bash
./experiment4/run.sh
```

For a quick single-repeat check:

```bash
REPEATS=1 ./experiment4/run.sh
```
