#!/usr/bin/env bash
set -euo pipefail
E1="$(cd "$(dirname "$0")" && pwd)"
CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
CODES_EXE="$CODES_BUILD/src/model-net-fluid-flow-wan-trace-traffic"
CASE="$E1/results/correctness"
SIMGRID_EXE="$E1/simgrid-flow-benchmark"
"$E1/setup.sh"
rm -rf "$CASE" "$E1/analysis"
mkdir -p "$CASE" "$E1/analysis"
cp "$E1/inputs/topology.yaml" "$CASE/topology.yaml"
cp "$E1/inputs/traffic.csv" "$CASE/traffic.csv"
cp "$E1/inputs/codes.yaml" "$CASE/codes.yaml"
cp "$E1/inputs/platform.xml" "$CASE/platform.xml"
CXX="${CXX:-c++}"
# shellcheck disable=SC2046
"$CXX" -std=c++17 -O2 -I"$(brew --prefix boost)/include" "$E1/simgrid-flow-benchmark.cpp" -o "$SIMGRID_EXE" $(pkg-config --cflags --libs simgrid)

echo "[1] Running CODES dynamic flow-sharing case"
(
    cd "$CODES_BUILD"
    mpirun -np 1 "$CODES_EXE" --sync=1 -- "$CASE/codes.yaml"
) > "$CASE/codes.out" 2>&1

echo "[1] Running SimGrid analytical flow-sharing case"
"$SIMGRID_EXE" \
    --cfg=network/model:CM02 \
    --cfg=network/TCP-gamma:0 \
    --cfg=network/weight-S:0 \
    --cfg=network/crosstraffic:0 \
    "$CASE/platform.xml" "$CASE/traffic.csv" "$CASE/simgrid-fct.csv" \
    > "$CASE/simgrid.out" 2>&1

echo "[1] Comparing analytical, CODES, and SimGrid results"
python3 "$E1/analyze.py" \
    "$CASE/fluid-segment-events.csv" \
    "$CASE/simgrid-fct.csv" \
    "$E1/analysis/interval-comparison.csv" \
    | tee "$E1/analysis/correctness-summary.csv"
