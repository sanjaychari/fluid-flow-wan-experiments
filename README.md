# Fluid-Flow WAN Experiments

This repository contains standalone scripts, configurations, input data, and
analysis utilities for evaluating the CODES Fluid-Flow WAN model. CODES and
ROSS are external dependencies and are not vendored here.

The experiment scripts default to:

```text
CODES_ROOT=$HOME/codes
CODES_BUILD=$HOME/codes/build
ROSS_ROOT=$HOME/ross
```

These paths can be overridden with environment variables.

## Repository layout

- `experiment1/` — mixed persistent/bursty dynamic-sharing correctness against analytical max-min allocation and SimGrid
- `experiment2/` — congestion, finite buffering, PAUSE, incast, and victim-flow experiments
- `experiment3/` — fluid-versus-packet CODES simulator-throughput comparison
- `experiment4/` — fixed-128-switch CODES-versus-SimGrid flow-density runtime comparison
- `experiment5/` — sequential-versus-conservative ROSS parallel scalability
- `common/` — shared topology, manifest, and CSV utilities

## 1. System prerequisites

The commands below target a recent Ubuntu system with OpenMPI. Equivalent
packages can be used on other Linux distributions.

```bash
sudo apt update
sudo apt install -y \
    build-essential cmake ninja-build git pkg-config \
    openmpi-bin libopenmpi-dev \
    flex bison \
    libzmq3-dev cppzmq-dev rapidjson-dev \
    python3 python3-venv python3-pip
```

Experiment 4 also requires SimGrid:

```bash
sudo apt install -y libsimgrid-dev
pkg-config --modversion simgrid
```

The SimGrid-based experiments use the `raw` network model. Experiment 1
uses equal-latency competing paths so its sharing semantics match the analytical
unweighted max-min reference.

## 2. Python environment

A dedicated Python environment is recommended because the CODES build uses the
PyTorch CMake package and the ZeroMQ server imports PyTorch and its Python-side
dependencies.

```bash
python3 -m venv "$HOME/.venvs/fluid-flow-wan"
source "$HOME/.venvs/fluid-flow-wan/bin/activate"
python -m pip install --upgrade pip
python -m pip install torch numpy pyzmq pandas scikit-learn
```

Keep this environment active while configuring CODES and while running
Experiment 3.

## 3. Build CODES from pull request 267 with PyTorch enabled

The Fluid-Flow WAN implementation used by these experiments is in CODES pull
request 267:

<https://github.com/codes-org/codes/pull/267>

Clone CODES, fetch the pull-request head, and check out the tested revision:

```bash
git clone https://github.com/codes-org/codes.git "$HOME/codes"
cd "$HOME/codes"
git fetch origin pull/267/head:local-expts

git checkout local-expts
```

Set torch_enable to 1 in codes/CODES-compile-instructions.sh.

Then compile CODES:

```
cd $HOME
cp "$HOME/codes/CODES-compile-instructions.sh" .
export CUDA_HOME=<enter your CUDA home directory here. Typically it is /usr/local/cuda>
bash CODES-compile-instructions.sh
```

The main executables used by the experiment scripts should then exist:

```bash
ls -l \
    "$HOME/codes/build/src/model-net-fluid-flow-wan-random-traffic" \
    "$HOME/codes/build/src/model-net-fluid-flow-wan-trace-traffic" \
    "$HOME/codes/build/src/model-net-synthetic"
```

## 4. Configure the experiment repository

Clone this repository to any location. The examples below use a neutral local
directory name:

```bash
git clone <repository-url> "$HOME/fluid-flow-wan-experiments"
cd "$HOME/fluid-flow-wan-experiments"
```

The defaults already match the installation layout above. To use different
paths:

```bash
export CODES_ROOT=/path/to/codes
export CODES_BUILD="$CODES_ROOT/build"
export ROSS_ROOT=/path/to/ross
```

## 5. Run Experiment 1

Experiment 1 uses a controlled two-switch WAN with multiple equal-hop
destinations. Three persistent bulk transfers are interleaved with six shorter
bursts, and dynamic max-min sharing is validated against both a closed-form
solution and SimGrid.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment1/setup.sh
./experiment1/run.sh
```

The primary summary is written to:

```text
experiment1/analysis/flow-comparison.csv
```

## 6. Run Experiment 2

Generate the deterministic topology and configuration matrix, then run the
sequential congestion experiments:

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment2/setup.sh
./experiment2/run_sequential.sh
```

The optional conservative-execution parity check is run separately:

```bash
./experiment2/run_conservative_check.sh
```

Primary summaries are written under `experiment2/analysis/`.

## 8. Run Experiment 3

Experiment 3 compares simulation throughput for matched offered data volumes
using the Fluid-Flow WAN model and the packet-based CODES baseline.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment3/setup.sh
REPEATS=3 ./experiment3/run_all.sh
```

The packet runs can take several minutes each. Primary summaries are written to
`experiment3/analysis/`.

## 9. Run Experiment 4

Experiment 4 fixes the network at 128 switches and compares CODES with SimGrid
while varying flow density at fixed offered volume and approximately fixed
workload span. The experiment isolates how the number of active persistent flows
and resulting rate-control events affect simulator runtime.

```bash
cd "$HOME/fluid-flow-wan-experiments"
REPEATS=3 ./experiment4/run.sh
```

The primary summary is:

```text
experiment4/results/experiment4-flow-density-summary.csv
```

It reports CODES and SimGrid simulation runtime, their runtime ratio,
flow count, represented start-time span and offered volume, and the CODES event
count.


## 10. Run Experiment 5

Experiment 5 holds one deterministic rate-fluid workload fixed and compares
sequential ROSS execution with conservative execution across increasing MPI rank
counts. It uses ROSS internal runtime, reports speedup and parallel efficiency,
and verifies canonical final flow-summary parity across execution modes.

```bash
cd "$HOME/fluid-flow-wan-experiments"
REPEATS=3 PARALLEL_RANKS="2 4 8" ./experiment5/run.sh
```

The primary summary is:

```text
experiment5/results/experiment5-parallel-scaling-summary.csv
```

## Re-running and preserving outputs

Each experiment can be rerun independently. Setup scripts regenerate
configuration/topology inputs where applicable, while run scripts place raw
outputs in the corresponding `results/` directory and analysis scripts write
compact CSV summaries under `analysis/` where provided.
