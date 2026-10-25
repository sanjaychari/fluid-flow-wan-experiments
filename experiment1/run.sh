#!/usr/bin/env bash
set -euo pipefail
E1="$(cd "$(dirname "$0")" && pwd)"
source "$E1/../common/env.sh"
CASE="$E1/results/correctness"; SIMGRID_EXE="$E1/simgrid-flow-benchmark"
"$E1/setup.sh"; rm -rf "$CASE" "$E1/analysis"; mkdir -p "$CASE" "$E1/analysis"
cp "$E1/inputs/topology.yaml" "$CASE/topology.yaml"; cp "$E1/inputs/flows.csv" "$CASE/flows.csv"; cp "$E1/inputs/codes.yaml" "$CASE/codes.yaml"; cp "$E1/inputs/platform.xml" "$CASE/platform.xml"
cp "$E1/inputs/traffic.csv" "$CASE/traffic.csv"
command -v pkg-config >/dev/null; pkg-config --exists simgrid
CFLAGS="$(pkg-config --cflags simgrid)"; LIBS="$(pkg-config --libs simgrid)"
if [[ "$(uname -s)" == Darwin ]] && command -v brew >/dev/null; then CFLAGS="$CFLAGS -I$(brew --prefix boost)/include"; fi
${CXX:-c++} -std=c++17 -O2 $CFLAGS "$E1/simgrid-flow-benchmark.cpp" -o "$SIMGRID_EXE" $LIBS
(
 cd "$CASE"; "$MPIEXEC" "$MPI_NP_FLAG" 1 "$RATE_BIN" --sync=1 -- codes.yaml
) > "$CASE/codes.out" 2>&1
"$SIMGRID_EXE" --cfg=network/model:raw "$CASE/platform.xml" "$CASE/traffic.csv" "$CASE/simgrid-fct.csv" > "$CASE/simgrid.out" 2>&1
python3 "$E1/analyze.py" "$CASE" | tee "$E1/analysis/correctness-summary.csv"
