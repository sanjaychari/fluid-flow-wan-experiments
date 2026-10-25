#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
if [[ $# -ne 3 ]]; then echo "usage: $0 POINT fluid|packet REPEAT|warmup" >&2; exit 2; fi
POINT="$1"; MODEL="$2"; REP="$3"
if [[ ! -f "$ROOT/cases.csv" ]] || ! grep -q "rate_fluid_wan:" "$ROOT/configs/fluid-small.yaml" 2>/dev/null; then "$ROOT/setup.sh"; fi
row=$(awk -F, -v p="$POINT" 'NR>1 && $1==p {print; exit}' "$ROOT/cases.csv"); row="${row//$'\r'/}"
[[ -n "$row" ]] || { echo "unknown point $POINT" >&2; exit 2; }
IFS=, read -r _ nmsg payload hosts target fcfg ftrace pcfg <<< "$row"
leaf="repeat$REP"; [[ "$REP" == warmup ]] && leaf=warmup
OUT="$ROOT/results/$POINT/$MODEL/$leaf"; rm -rf "$OUT"; mkdir -p "$OUT"

if [[ "$MODEL" == fluid ]]; then
    require_executable "$RATE_BIN"
    mkdir -p "$OUT/logs"
    cp "$ROOT/$fcfg" "$OUT/config.yaml"; cp "$ROOT/$ftrace" "$OUT/flows.csv"; cp "$ROOT/topologies/fluid-dragonfly.yaml" "$OUT/topology.yaml"
    cmd=("$MPIEXEC" "$MPI_NP_FLAG" 1 "$RATE_BIN" --sync=1 -- config.yaml)
    inputs=("$OUT/config.yaml" "$OUT/flows.csv" "$OUT/topology.yaml")
elif [[ "$MODEL" == packet ]]; then
    require_executable "$PACKET_BIN"
    cp "$ROOT/$pcfg" "$OUT/config.yaml"
    cmd=("$MPIEXEC" "$MPI_NP_FLAG" 1 "$PACKET_BIN" --sync=1 --traffic=2 "--num_messages=$nmsg" "--payload_size=$payload" -- config.yaml)
    inputs=("$OUT/config.yaml")
else
    echo "model must be fluid or packet" >&2; exit 2
fi

echo "[E3] $POINT $MODEL $leaf"

# Python time_ns() is portable across macOS and Linux; macOS date does not
# support GNU date's %N nanosecond conversion.
start_ns=$(python3 -c 'import time; print(time.time_ns())')

set +e
if [[ "$(uname -s)" == "Darwin" ]]; then
    # BSD/macOS time: -l prints resource usage and -o writes it to a file.
    (cd "$OUT" && /usr/bin/time -l -o resource.txt "${cmd[@]}") > "$OUT/model-output.log" 2>&1
else
    # GNU time: -v prints verbose resource usage.
    (cd "$OUT" && /usr/bin/time -v -o resource.txt "${cmd[@]}") > "$OUT/model-output.log" 2>&1
fi
rc=$?
set -e

end_ns=$(python3 -c 'import time; print(time.time_ns())')
wall=$(python3 - "$start_ns" "$end_ns" <<'PY'
import sys
print((int(sys.argv[2]) - int(sys.argv[1])) / 1e9)
PY
)
manifest_args=(); for p in "${inputs[@]}"; do manifest_args+=(--input "$p"); done
python3 "$ROOT/../common/write_manifest.py" --output "$OUT/manifest.json" \
    --codes-root "$CODES_ROOT" --ross-root "$ROSS_ROOT" --command "${cmd[*]}" \
    --sync 1 --ranks 1 --mode "$MODEL" --wall-clock-sec "$wall" --return-code "$rc" \
    --interval-seconds "0" --note "target_gbit=$target" \
    "${manifest_args[@]}"
(( rc == 0 )) || { tail -100 "$OUT/model-output.log" >&2; exit "$rc"; }
