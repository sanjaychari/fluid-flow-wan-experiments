#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "usage: $0 CASE [SYNC=1] [NP=1]" >&2
    exit 2
fi
CASE="$1"; SYNC="${2:-1}"; NP="${3:-1}"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
row=$(awk -F, -v c="$CASE" 'NR>1 && $1==c {print; exit}' "$ROOT/cases.csv")
row="${row//$'\r'/}"
[[ -n "$row" ]] || { echo "unknown case: $CASE" >&2; exit 2; }
IFS=, read -r _ scenario seed workload config topology trace <<< "$row"

if [[ "$workload" == random ]]; then BIN="$RANDOM_BIN"; else BIN="$TRACE_BIN"; fi
require_executable "$BIN"

OUT="$ROOT/results/$scenario/seed$seed/$CASE/sync${SYNC}-np${NP}"
rm -rf "$OUT"
mkdir -p "$OUT/logs"
cp "$ROOT/$config" "$OUT/config.yaml"
cp "$ROOT/$topology" "$OUT/topology.yaml"
inputs=("$OUT/config.yaml" "$OUT/topology.yaml")
if [[ -n "$trace" ]]; then
    cp "$ROOT/$trace" "$OUT/traffic.csv"
    inputs+=("$OUT/traffic.csv")
fi

cmd=("$MPIEXEC" "$MPI_NP_FLAG" "$NP" "$BIN" "--sync=$SYNC" -- config.yaml)
printf '[E2] %s sync=%s np=%s\n' "$CASE" "$SYNC" "$NP"
start_ns=$(date +%s%N)
set +e
(cd "$OUT" && "${cmd[@]}") > "$OUT/model-output.log" 2>&1
rc=$?
set -e
end_ns=$(date +%s%N)
wall=$(python3 - "$start_ns" "$end_ns" <<'PY'
import sys
print((int(sys.argv[2])-int(sys.argv[1]))/1e9)
PY
)
manifest_args=()
for p in "${inputs[@]}"; do manifest_args+=(--input "$p"); done
python3 "$ROOT/../common/write_manifest.py" \
    --output "$OUT/manifest.json" --codes-root "$CODES_ROOT" --ross-root "$ROSS_ROOT" \
    --command "${cmd[*]}" --sync "$SYNC" --ranks "$NP" --mode pdes \
    --seed "$seed" --interval-seconds 10 --wall-clock-sec "$wall" --return-code "$rc" \
    "${manifest_args[@]}"
(( rc == 0 )) || { tail -100 "$OUT/model-output.log" >&2; exit "$rc"; }
