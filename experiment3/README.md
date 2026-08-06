# Experiment 3 — fluid vs packet-based CODES simulator throughput

This is a **computational-granularity comparison, not a fidelity comparison**.
Both workloads use a matched regular Dragonfly-scale platform:

- 264 routers/switches, 1056 endpoints, 4 endpoints/router
- 33 groups × 8 routers/group
- local and terminal links: 42 Gbps
- global links: 37.6 Gbps
- minimal routing
- deterministic nearest-group traffic in logical host numbering: `dst=(src+32)%1056`
- sequential execution

The packet baseline keeps the stock 512-byte packet and 32-byte chunk settings.
The matched volume points use 1, 2, and 4 messages/host with 262144-byte
application messages, corresponding to 2.214592512, 4.429185024, and
8.858370048 aggregate Gbit.

`run_all.sh` performs one warm-up and at least three measured runs per model and
point. The analyzer uses `target_gbit` from `cases.csv` for both models so the
throughput denominator is exactly the matched offered application volume.
