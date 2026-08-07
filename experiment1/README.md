# Experiment 1 — ESNet digital-twin validation

This directory reruns the eight archived June 7, 2024 ESNet validation
experiments used for the Fluid-Flow WAN evaluation.

The committed `inputs/` files are the exact normalized inputs from the archived
validation artifact:

- one common four-switch/eight-terminal ESNet logical topology with 200-Gbps host-facing links, 400-Gbps inter-switch links, and 909.28-Mbit shared switch buffers;
- one CODES configuration per physical experiment;
- the sender-side 100 ms Fluid-Flow WAN traffic trace used by CODES;
- the physical receiver-side 1 s volume reference used for validation; and
- the archived physical sender/receiver totals for each flow.

The original 1 s iperf sender volumes had already been split uniformly across
ten 100 ms fluid intervals in the archived `traffic-trace.csv` files. The run
scripts intentionally use these exact traces instead of regenerating them.
Each `offered_gbit` value is therefore sender-side application traffic supplied
to the source terminal during one 100 ms simulation interval. The subdivision
preserves every measured 1 s sender total and assumes uniform transmission
within that 1 s observation window.

The common logical topology uses 200-Gbps terminal-facing links, 400-Gbps
inter-switch links, and a 909.28-Mbit shared buffer per modeled switch. The
traffic traces are not scaled to those capacities: they replay the measured
iperf sender volumes.

## Scenarios

| Run | Physical traffic pattern |
| --- | --- |
| 1 | STAR-DTN-1 -> STAR-DTN-2, direct VLAN4012 |
| 2 | LBNL-DTN-1 -> LBNL-DTN-2, direct VLAN4012 |
| 3 | LBNL-DTN-1 -> STAR-DTN-1, direct VLAN4012 |
| 4 | LBNL-DTN-2 -> STAR-DTN-2, direct VLAN4012 |
| 5 | LBNL1->LBNL2 plus STAR1->STAR2 starting 61 s later |
| 6 | STAR1 VLAN3002 -> STAR2 VLAN3001 through StarLight |
| 7 | LBNL1->LBNL2 plus routed STAR1->STAR2 starting 3 s later |
| 8 | LBNL1->STAR1; routed LBNL2->LBNL1 at +2 s; routed STAR1->STAR2 at +4 s |

All runs use sequential ROSS (`--sync=1`) with `interval_seconds=0.1`, the
archived send horizon, 20 drain intervals, 1 ms backpressure control delay, and
PDES egress.

## Validation metrics

For every physical flow the analyzer reports:

1. whole-run delivered-volume relative error against the physical receiver
   total;
2. raw 1 s NMAE; and
3. delay-adjusted 1 s NMAE.

The delay adjustment is **not fit to the output**. It is derived from the
modeled path length. A direct same-switch flow is shifted by two 100 ms data
intervals. A routed flow crossing two switch-to-switch links is shifted by four
100 ms intervals. In general the shift is:

`2 + number_of_switch_to_switch_hops` fluid intervals.

The analyzer also checks that each run ends with zero source backlog, zero
switch ready/shared-buffer occupancy, and zero permanent drops.

Acceptance thresholds are the predeclared study values:

- whole-run delivered-volume relative error <= 1%;
- delay-adjusted 1 s NMAE <= 10%;
- residual source backlog = 0;
- residual switch queue/buffer = 0; and
- CODES drops = 0.

`reference-results/validation-summary.csv` contains the archived July 2026
results for regression comparison. The rerun results are written under
`results/` and analysis tables under `analysis/`.

## Run

From the repository root:

```bash
./experiment1/setup.sh
./experiment1/run.sh
```

To rerun only selected physical experiments:

```bash
RUNS="1 6 8" ./experiment1/run.sh
```

By default the script analyzes all result directories that are present. Run the
analyzer explicitly with:

```bash
python3 experiment1/analyze.py
```
