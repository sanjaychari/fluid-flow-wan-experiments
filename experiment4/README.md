# Experiment 4

External flow-level simulator comparison between the CODES fluid-flow WAN model and SimGrid.

Defaults:
- CODES source: `~/codes`
- CODES build: `~/codes/build`
- results: `./results`
- SimGrid selected through system `pkg-config`

For a pilot, generate and run only the 32-switch case before invoking `run.sh` for the full sweep.

`run.sh` performs two related performance studies:

1. the existing 32/64/128-switch CODES-versus-SimGrid scale comparison at a
   1-s fluid interval; and
2. an interval-sensitivity subset at 128 switches using 1-s, 10-s, and 100-s
   fluid intervals by default.

The interval subset regenerates the SimGrid platform for each interval so that
its nonzero per-hop latency matches the CODES fluid interval.  Each interval is
calibrated independently, and timed CODES results are accepted only after all
500-Gbit terminal flows have drained.

The interval subset can be customized or disabled, for example:

```bash
INTERVAL_SWEEP_SCALE=128 \
INTERVAL_SWEEP_SECONDS="1 10 100" \
./experiment4/run.sh

RUN_INTERVAL_SWEEP=0 ./experiment4/run.sh
```

To run only the new interval-sensitivity subset without repeating the existing
32/64/128-switch scale sweep:

```bash
RUN_SCALE_SWEEP=0 ./experiment4/run.sh
```


## Committed results

The `results/` directory contains the exact generated topologies, workloads,
configurations, correctness outputs, calibration evidence, and measured runtime
outputs used by the analysis scripts. These text artifacts are intended to be
committed.

`run.sh` and `run_correctness.sh` invoke `sanitize_results.py` after a run. The
sanitizer replaces local absolute CODES/repository paths with stable anonymous
paths:

- `/workspace/codes`
- `/workspace/fluid-flow-wan-experiments`

The generated `simgrid-flow-benchmark` executable is a local build artifact and
should not be committed; rebuild it from `simgrid-flow-benchmark.cpp`.

The two performance summaries are:

```text
results/experiment4-performance-summary.csv
results/experiment4-interval-sweep-summary.csv
```
