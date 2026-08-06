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

- `experiment1/` — ESNet trace-driven validation
- `experiment2/` — congestion, finite buffering, PAUSE, incast, and victim-flow experiments
- `experiment3/` — fluid-versus-packet CODES simulator-throughput comparison
- `experiment4/` — CODES-versus-SimGrid flow-level comparison
- `common/` — shared topology, manifest, and CSV utilities

Generated results may be committed after anonymization. Before staging new
or rerun outputs, run:

```bash
python3 common/anonymize_repository.py --apply
```

The sanitizer canonicalizes local checkout paths and manifest host fields, then
audits the repository for remaining machine-specific identifiers.

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

The Experiment 4 scripts were exercised with SimGrid 3.30 and configure CM02
for unweighted max-min sharing.

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

Experiment 1 replays the committed ESNet validation inputs and analyzes all
eight scenarios.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment1/setup.sh
./experiment1/run.sh
```

Primary summaries are written to:

```text
experiment1/analysis/experiment1-headline.csv
experiment1/analysis/experiment1-run-summary.csv
experiment1/analysis/experiment1-flow-summary.csv
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

Experiment 4 first checks a controlled two-flow max-min allocation and then
runs the CODES/SimGrid performance comparison. The performance runner also
includes an interval-sensitivity subset at the 128-switch scale using 1-s,
10-s, 60-s, and 3600-s fluid intervals by default. The 60-s and 3600-s
points represent one-minute and one-hour temporal aggregation, respectively.
Only the CODES fluid interval changes in this sweep. The SimGrid reference
platform remains fixed at 1-s per-hop latency for every interval point; SimGrid
does not use the CODES fluid-interval parameter.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment4/run_correctness.sh
./experiment4/run.sh
```

The performance summary is written to:

```text
experiment4/results/experiment4-performance-summary.csv
experiment4/results/experiment4-interval-sweep-summary.csv
```

Experiment 4 text results are intended to be committed after the repository-wide
anonymization pass. The locally compiled `experiment4/simgrid-flow-benchmark`
binary remains ignored and should be rebuilt from source.

## Re-running and preserving outputs

Each experiment can be rerun independently. Setup scripts regenerate
configuration/topology inputs where applicable, while run scripts place raw
outputs in the corresponding `results/` directory and analysis scripts write
compact CSV summaries under `analysis/` where provided.

Before staging generated outputs, run the repository-wide anonymization and
audit:

```bash
python3 common/anonymize_repository.py --apply
```

A nonzero exit means a local path, username, hostname, email address, or
non-anonymous manifest host still needs review.
