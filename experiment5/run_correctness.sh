#!/usr/bin/env bash
set -euo pipefail

E5="$(cd "$(dirname "$0")" && pwd)"
CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
CODES_EXE="$CODES_BUILD/src/model-net-fluid-flow-wan-trace-traffic"

CASE="$E5/results/correctness"
SIMGRID_EXE="$E5/simgrid-flow-benchmark"

[[ -x "$CODES_EXE" ]] || {
    echo "missing CODES executable: $CODES_EXE" >&2
    exit 1
}

rm -rf "$CASE"

python3 "$E5/generate_correctness_case.py"

# Link explicitly against the installed system SimGrid library so the run does
# not depend on a particular pkg-config environment.
g++ -std=c++17 -O2 \
    "$E5/simgrid-flow-benchmark.cpp" \
    -o "$SIMGRID_EXE" \
    -lsimgrid

echo "[5A] Running CODES max-min correctness case"
(
    cd "$CODES_BUILD"
    mpirun -np 1 \
        "$CODES_EXE" \
        --sync=1 -- \
        "$CASE/codes.yaml"
) > "$CASE/codes.out" 2>&1

echo "[5A] Running SimGrid max-min correctness case"
"$SIMGRID_EXE" \
    --cfg=network/model:CM02 \
    --cfg=network/TCP-gamma:0 \
    --cfg=network/weight-S:0 \
    --cfg=network/crosstraffic:0 \
    "$CASE/platform.xml" \
    "$CASE/traffic.csv" \
    "$CASE/simgrid-fct.csv" \
    > "$CASE/simgrid.out" 2>&1

echo "[5A] Correctness result"
python3 "$E5/analyze_correctness.py" \
    "$CASE/flowlet-events.csv" \
    "$CASE/simgrid-fct.csv" \
    | tee "$CASE/correctness-summary.csv"

python3 "$E5/sanitize_results.py" \
    --results "$E5/results" \
    --codes-root "$CODES_ROOT" \
    --repo-root "$E5/.."
