#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
if [[ $# -ne 3 ]]; then echo "usage: $0 POINT fluid|packet REPEAT|warmup" >&2; exit 2; fi
POINT="$1"; MODEL="$2"; REP="$3"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
row=$(awk -F, -v p="$POINT" 'NR>1 && $1==p {print; exit}' "$ROOT/cases.csv"); row="${row//$'\r'/}"
[[ -n "$row" ]] || { echo "unknown point $POINT" >&2; exit 2; }
IFS=, read -r _ nmsg payload hosts target fcfg ftrace pcfg <<< "$row"
leaf="repeat$REP"; [[ "$REP" == warmup ]] && leaf=warmup
OUT="$ROOT/results/$POINT/$MODEL/$leaf"; rm -rf "$OUT"; mkdir -p "$OUT"

if [[ "$MODEL" == fluid ]]; then
    require_executable "$TRACE_BIN"
    mkdir -p "$OUT/logs"
    cp "$ROOT/$fcfg" "$OUT/config.yaml"; cp "$ROOT/$ftrace" "$OUT/traffic.csv"; cp "$ROOT/topologies/fluid-dragonfly.yaml" "$OUT/topology.yaml"
    cmd=("$MPIEXEC" "$MPI_NP_FLAG" 1 "$TRACE_BIN" --sync=1 -- config.yaml)
    inputs=("$OUT/config.yaml" "$OUT/traffic.csv" "$OUT/topology.yaml")
elif [[ "$MODEL" == packet ]]; then
    require_executable "$PACKET_BIN"
    cp "$ROOT/$pcfg" "$OUT/config.yaml"
    cmd=("$MPIEXEC" "$MPI_NP_FLAG" 1 "$PACKET_BIN" --sync=1 --traffic=2 "--num_messages=$nmsg" "--payload_size=$payload" -- config.yaml)
    inputs=("$OUT/config.yaml")
else
    echo "model must be fluid or packet" >&2; exit 2
fi

echo "[E4] $POINT $MODEL $leaf"
start_ns=$(date +%s%N)
set +e
(cd "$OUT" && /usr/bin/time -v -o resource.txt "${cmd[@]}") > "$OUT/model-output.log" 2>&1
rc=$?
set -e
end_ns=$(date +%s%N)
wall=$(python3 - "$start_ns" "$end_ns" <<'PY'
import sys
print((int(sys.argv[2])-int(sys.argv[1]))/1e9)
PY
)
manifest_args=(); for p in "${inputs[@]}"; do manifest_args+=(--input "$p"); done
python3 "$ROOT/../common/write_manifest.py" --output "$OUT/manifest.json" \
    --codes-root "$CODES_ROOT" --ross-root "$ROSS_ROOT" --command "${cmd[*]}" \
    --sync 1 --ranks 1 --mode "$MODEL" --wall-clock-sec "$wall" --return-code "$rc" \
    --interval-seconds "$([[ "$MODEL" == fluid ]] && echo 1 || echo 0)" --note "target_gbit=$target" \
    "${manifest_args[@]}"
(( rc == 0 )) || { tail -100 "$OUT/model-output.log" >&2; exit "$rc"; }
