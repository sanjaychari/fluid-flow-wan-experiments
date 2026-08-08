# Experiment 1 — Dynamic flow-sharing correctness

This experiment validates the Fluid-Flow WAN model against an analytical
max-min solution and SimGrid's CM02 analytical flow-level model.

The CODES case uses the same four-switch/eight-terminal ESnet topology
abstraction used by the earlier testbed experiment:

- 200-Gbps terminal-facing links;
- 400-Gbps inter-switch links; and
- 909.28-Mbit shared switch buffers.

The correctness workload exercises the `VLAN4012` portion of that topology.
Terminals 0, 1, and 2 send persistent flows to terminal 3, so all active flows
share the same 200-Gbps switch-to-terminal output link.

## Workload

| Flow | Source | Destination | Start interval | Size |
| --- | ---: | ---: | ---: | ---: |
| A / 1 | 0 | 3 | 0 | 500 Gbit |
| B / 2 | 1 | 3 | 0 | 40 Gbit |
| C / 3 | 2 | 3 | 10 | 200 Gbit |

The fluid interval is 100 ms. CODES retains its normal 1-ms control-event
delay. PAUSE uses the standard 0.80/0.50 high/low watermarks.

## Analytical solution

The shared output capacity is 200 Gbps * 0.1 s = 20 Gbit per interval.

Expected service at the common bottleneck:

```text
relative intervals  0-3   : A=10 Gbit, B=10 Gbit
relative intervals  4-9   : A=20 Gbit
relative intervals 10-29  : A=10 Gbit, C=10 Gbit
relative intervals 30-36  : A=20 Gbit
```

Expected completion times:

```text
A: 3.7 s
B: 0.4 s
C: 3.0 s
```

## Run

```bash
./experiment1/setup.sh
./experiment1/run.sh
```
