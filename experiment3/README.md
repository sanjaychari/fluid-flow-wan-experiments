# Experiment 3 — Rate-fluid vs packet-based CODES throughput

Computational-granularity comparison, not a fidelity comparison. The same 264-router/1056-endpoint Dragonfly-scale topology and matched application volumes are retained. The fluid side now uses `model-net-rate-fluid-wan`; each host contributes one finite flow whose size equals the matched packet workload volume. Runtime, event count, events/Gbit, and simulated Gbit/wall-second remain the primary metrics.

Run: `./experiment3/setup.sh && ./experiment3/run_all.sh`.

The rate-fluid side uses the common 5-ms one-way per-link latency; this experiment is computational, not a fidelity comparison.
