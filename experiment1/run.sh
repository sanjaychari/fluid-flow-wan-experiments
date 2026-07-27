#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"

require_executable "$TRACE_BIN"
"$ROOT/setup.sh"

RUNS="${RUNS:-1 2 3 4 5 6 7 8}"

for run in $RUNS; do
    case "$run" in
        1|2|3|4|5|6|7|8) ;;
        *) echo "invalid Experiment 1 run: $run" >&2; exit 1 ;;
    esac

    src="$ROOT/inputs/run$run"
    out="$ROOT/results/run$run"

    rm -rf "$out"
    mkdir -p "$out/logs"

    cp "$src/config.yaml" "$out/config.yaml"
    cp "$src/traffic-trace.csv" "$out/traffic-trace.csv"
    cp "$src/receiver-reference.csv" "$out/receiver-reference.csv"
    cp "$src/physical-summary.csv" "$out/physical-summary.csv"
    cp "$ROOT/inputs/esnet-fluid-flow-wan-topology.yaml" \
       "$out/esnet-fluid-flow-wan-topology.yaml"

    echo "[Experiment 1] run $run"

    start_ns=$(date +%s%N)
    set +e
    (
        cd "$out"
        "$MPIEXEC" "$MPI_NP_FLAG" 1 \
            "$TRACE_BIN" --sync=1 -- config.yaml
    ) > "$out/model-output.log" 2>&1
    rc=$?
    set -e
    end_ns=$(date +%s%N)

    wall=$(python3 - "$start_ns" "$end_ns" <<'PY'
import sys
print((int(sys.argv[2]) - int(sys.argv[1])) / 1e9)
PY
)

    python3 "$ROOT/../common/write_manifest.py" \
        --output "$out/manifest.json" \
        --codes-root "$CODES_ROOT" \
        --ross-root "$ROSS_ROOT" \
        --command "$MPIEXEC $MPI_NP_FLAG 1 $TRACE_BIN --sync=1 -- config.yaml" \
        --sync 1 \
        --ranks 1 \
        --mode pdes \
        --wall-clock-sec "$wall" \
        --return-code "$rc" \
        --interval-seconds 0.1 \
        --input "$out/config.yaml" \
        --input "$out/esnet-fluid-flow-wan-topology.yaml" \
        --input "$out/traffic-trace.csv" \
        --input "$out/receiver-reference.csv" \
        --input "$out/physical-summary.csv"

    if (( rc != 0 )); then
        echo "Experiment 1 run $run failed (rc=$rc)" >&2
        tail -100 "$out/model-output.log" >&2
        exit "$rc"
    fi

done

python3 "$ROOT/analyze.py"
