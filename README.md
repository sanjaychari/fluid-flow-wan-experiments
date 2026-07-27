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
- `experiment3/` — synchronous ZeroMQ external-computation overhead
- `experiment4/` — fluid-versus-packet CODES simulator-throughput comparison
- `experiment5/` — CODES-versus-SimGrid flow-level comparison
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

Experiment 5 also requires SimGrid:

```bash
sudo apt install -y libsimgrid-dev
pkg-config --modversion simgrid
```

The Experiment 5 scripts were exercised with SimGrid 3.30 and configure CM02
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

## 3. Build ROSS

The CODES pull-request CI currently pins ROSS to the commit below. Using the
same commit makes the dependency version explicit.

```bash
git clone https://github.com/ROSS-org/ROSS.git "$HOME/ross"
git -C "$HOME/ross" checkout 9b6ccb18f9b9db438bf41b5b221d0ef16a4dac48

cmake -S "$HOME/ross" -B "$HOME/ross/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DROSS_BUILD_MODELS=ON \
    -DCMAKE_INSTALL_PREFIX="$HOME/ross/install"

cmake --build "$HOME/ross/build" --target install -j2
```

## 4. Build CODES from pull request 267 with PyTorch enabled

The Fluid-Flow WAN implementation used by these experiments is in CODES pull
request 267:

<https://github.com/codes-org/codes/pull/267>

Clone CODES, fetch the pull-request head, and check out the tested revision:

```bash
git clone https://github.com/codes-org/codes.git "$HOME/codes"
cd "$HOME/codes"
git fetch origin pull/267/head

git checkout e4b90e1708869faba1b903c657a3d95504eb9092
```

If a later revision of pull request 267 is intentionally being tested, replace
the commit above with that revision and record it with the results.

Locate the PyTorch CMake package from the active Python environment:

```bash
export Torch_DIR="$(python3 -c 'import torch; print(torch.utils.cmake_prefix_path)')/Torch"
```

Configure CODES with both PyTorch and ZeroMQ explicitly enabled. The other
optional workload packages are disabled because these experiments do not
require them.

```bash
cd "$HOME/codes"
rm -rf build

cmake -S . -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=ON \
    -DCODES_USE_TORCH=ON \
    -DCODES_USE_ZEROMQ=ON \
    -DCODES_USE_SWM=OFF \
    -DCODES_USE_UNION=OFF \
    -DCODES_USE_DUMPI=OFF \
    -DCMAKE_PREFIX_PATH="$HOME/ross/install" \
    -DTorch_DIR="$Torch_DIR"

cmake --build build -j2
```

During configuration, verify that CMake reports both of these features as
enabled:

```text
Torch ML models enabled
ZeroMQ director-client/zmqml surrogate enabled
```

The main executables used by the experiment scripts should then exist:

```bash
ls -l \
    "$HOME/codes/build/src/model-net-fluid-flow-wan-random-traffic" \
    "$HOME/codes/build/src/model-net-fluid-flow-wan-trace-traffic" \
    "$HOME/codes/build/src/model-net-synthetic"
```

## 5. Configure the experiment repository

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

## 6. Run Experiment 1

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

## 7. Run Experiment 2

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

Experiment 3 compares local egress computation with the same analytical
calculation performed synchronously through the ZeroMQ backend. It does not
train a model.

Keep the Python environment from Section 2 active, then run:

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment3/setup.sh

REPEATS=5 RUN_DIAGNOSTICS=1 \
    ./experiment3/run_all.sh
```

The runner owns the ZeroMQ server lifecycle. Do not leave another server bound
to the configured endpoint before starting the experiment.

Primary summaries are written to:

```text
experiment3/analysis/experiment3-runs.csv
experiment3/analysis/experiment3-summary.csv
experiment3/analysis/experiment3-paired.csv
experiment3/analysis/experiment3-diagnostic-latency.csv
```

## 9. Run Experiment 4

Experiment 4 compares simulation throughput for matched offered data volumes
using the Fluid-Flow WAN model and the packet-based CODES baseline.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment4/setup.sh
REPEATS=3 ./experiment4/run_all.sh
```

The packet runs can take several minutes each. Primary summaries are written to
`experiment4/analysis/`.

## 10. Run Experiment 5

Experiment 5 first checks a controlled two-flow max-min allocation and then
runs the CODES/SimGrid performance comparison.

```bash
cd "$HOME/fluid-flow-wan-experiments"
./experiment5/run_correctness.sh
./experiment5/run.sh
```

The performance summary is written to:

```text
experiment5/results/experiment5-performance-summary.csv
```

Experiment 5 text results are intended to be committed after the repository-wide
anonymization pass. The locally compiled `experiment5/simgrid-flow-benchmark`
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
