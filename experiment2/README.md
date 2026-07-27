# Experiment 2 — large-network congestion and backpressure

Fixed science platform:

- 64 switches, 2 terminals/switch (128 terminals)
- average directed out-degree 4.0, reverse-link probability 0.50
- 10–30 Gbps switch links, 100 Gbps terminal links
- 10 s data interval, 1 ms control/backpressure delay
- topology seed 12345
- sequential (`--sync=1`) for science results

The setup creates the four scenario families from the experiment plan:

- A: low / medium / high load, traffic seeds 2001–2003
- B: 25 / 100 / 400 Gb shared buffers × aggressive (0.50/0.30) or moderate (0.80/0.50) PAUSE × three seeds
- C: 4 / 8 / 16-source persistent incast × three deterministic source-set seeds
- D: 8 elephant flows plus one 1 Gbps victim across S45->S44, with the direct reverse edge absent versus present at the same bottleneck bandwidth

```bash
./experiment2/setup.sh
./experiment2/run_sequential.sh
./experiment2/run_conservative_check.sh   # optional parity/parallelization evidence
```
