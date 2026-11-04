# Experiment 5 — Sequential versus conservative scaling

Experiment 5 measures parallel scalability of the rate-based Fluid-Flow WAN
workload in ROSS. A single deterministic workload is held fixed while execution
changes from sequential ROSS (`--sync=1`, one MPI rank) to conservative ROSS
(`--sync=2`) at increasing MPI rank counts.

The default case uses 512 switches, 1024 terminals, 4096 finite flows, and
5-ms one-way link latency. PAUSE and debug logging are disabled so the
experiment measures synchronization/scaling behavior rather than debug I/O or a
particular congestion episode. The topology, flow trace, simulated horizon, and
all model parameters are identical across rank counts.

ROSS's own `Running Time` is the primary runtime measurement. This excludes
`mpirun` process-launch overhead, which is important when comparing sequential
and multi-rank execution. The summary reports:

- mean ROSS runtime;
- speedup relative to the one-rank sequential baseline;
- parallel efficiency (`speedup / ranks`);
- mean committed (`Net Events Processed`) event count; and
- exact parity of a canonicalized final flow-summary checksum.

Optimistic execution is intentionally not part of this experiment.

Run the default 1/2/4/8-rank study with three repeats:

```bash
./experiment5/run.sh
```

For a quick check:

```bash
REPEATS=1 PARALLEL_RANKS="2 4" ./experiment5/run.sh
```

The workload size can be overridden without editing the scripts:

```bash
SWITCHES=1024 FLOWS=8192 REPEATS=3 PARALLEL_RANKS="2 4 8 16" \
    ./experiment5/run.sh
```

The primary result is:

```text
experiment5/results/experiment5-parallel-scaling-summary.csv
```

### Optimistic debug output

With debug logging enabled, optimistic ROSS executions may print repeated or
apparently contradictory event messages. Debug messages are emitted when
speculative events execute and cannot be retracted when those events are
subsequently rolled back. The committed simulation state should therefore be
assessed from final outputs/statistics rather than the raw ordering or
multiplicity of optimistic debug messages.
