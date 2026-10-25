# Experiment 2 — Large-network congestion and backpressure

Retains the four original scenario families on the fixed 64-switch/128-terminal topology: A) load, B) buffer size × PAUSE policy, C) incast fan-in, and D) elephant/victim asymmetry. The new workload is finite-flow/trace driven because `model-net-rate-fluid-wan` does not have the old interval random-traffic generator. Paired seeds and topology treatments are retained. CODES-native destination FCT, maximum switch-buffer occupancy, dropped volume, and PAUSE activity are summarized.

Run: `./experiment2/setup.sh && ./experiment2/run_sequential.sh`.

All cases use the common 5-ms one-way per-link latency.
