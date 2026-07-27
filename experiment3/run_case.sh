#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 CASE REPEAT [performance|diagnostic]" >&2; exit 2
fi
CASE="$1"; REP="$2"; KIND="${3:-performance}"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
row=$(awk -F, -v c="$CASE" 'NR>1 && $1==c {print; exit}' "$ROOT/cases.csv")
row="${row//$'\r'/}"
[[ -n "$row" ]] || { echo "unknown case: $CASE" >&2; exit 2; }
IFS=, read -r _ switches terminals load mode seed config topology <<< "$row"
require_executable "$RANDOM_BIN"

if [[ "$REP" == warmup ]]; then
    leaf="warmup"
elif [[ "$KIND" == diagnostic ]]; then
    leaf="diagnostic"
else
    leaf="repeat$REP"
fi
OUT="$ROOT/results/scale${switches}/$load/$mode/$leaf"
rm -rf "$OUT"; mkdir -p "$OUT/logs"
cp "$ROOT/$config" "$OUT/config.yaml"
cp "$ROOT/$topology" "$OUT/topology.yaml"
if [[ "$KIND" == diagnostic ]]; then
    python3 - "$OUT/config.yaml" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); t=p.read_text(); t,n=re.subn(r'(?m)^(\s*debug_prints:\s*)0\s*$',r'\g<1>1',t,count=1)
if n != 1: raise SystemExit('could not enable debug_prints')
p.write_text(t)
PY
fi
cmd=("$MPIEXEC" "$MPI_NP_FLAG" 1 "$RANDOM_BIN" --sync=1 -- config.yaml)
echo "[E3] $CASE $leaf"
start_ns=$(date +%s%N)
set +e
(cd "$OUT" && ZMQML_ENDPOINT="$ZMQ_CLIENT_ENDPOINT" "${cmd[@]}") > "$OUT/model-output.log" 2>&1
rc=$?
set -e
end_ns=$(date +%s%N)
wall=$(python3 - "$start_ns" "$end_ns" <<'PY'
import sys
print((int(sys.argv[2])-int(sys.argv[1]))/1e9)
PY
)
python3 "$ROOT/../common/write_manifest.py" \
    --output "$OUT/manifest.json" --codes-root "$CODES_ROOT" --ross-root "$ROSS_ROOT" \
    --command "ZMQML_ENDPOINT=$ZMQ_CLIENT_ENDPOINT ${cmd[*]}" --sync 1 --ranks 1 --mode "$mode" \
    --seed "$seed" --interval-seconds 10 --wall-clock-sec "$wall" --return-code "$rc" \
    --input "$OUT/config.yaml" --input "$OUT/topology.yaml" --note "load=$load" --note "pass=$KIND"
(( rc == 0 )) || { tail -120 "$OUT/model-output.log" >&2; exit "$rc"; }
