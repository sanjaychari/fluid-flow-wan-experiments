# Experiment 5

External flow-level simulator comparison between the CODES fluid-flow WAN model and SimGrid.

Defaults:
- CODES source: `~/codes`
- CODES build: `~/codes/build`
- results: `./results`
- SimGrid selected through system `pkg-config`

For a pilot, generate and run only the 32-switch case before invoking `run.sh` for the full sweep.


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
