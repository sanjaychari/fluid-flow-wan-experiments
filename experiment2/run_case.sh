#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; source "$ROOT/../common/env.sh"
[[ $# -ge 1 ]] || { echo "usage: $0 CASE [SYNC]" >&2; exit 2; }; NAME="$1"; SYNC="${2:-1}"
if [[ ! -f "$ROOT/cases.csv" ]] || ! head -1 "$ROOT/cases.csv" | grep -q "flow_file"; then "$ROOT/setup.sh"; fi
row=$(awk -F, -v n="$NAME" 'NR>1 && $1==n {print;exit}' "$ROOT/cases.csv"); [[ -n "$row" ]] || { echo "unknown case $NAME" >&2; exit 2; }
IFS=, read -r name scenario seed cfg topo flow <<< "$row"
OUT="$ROOT/results/$NAME/sync$SYNC"; rm -rf "$OUT"; mkdir -p "$OUT"
cp "$ROOT/$cfg" "$OUT/config.yaml"; cp "$ROOT/$topo" "$OUT/topology.yaml"; cp "$ROOT/$flow" "$OUT/flows.csv"
(cd "$OUT"; "$MPIEXEC" "$MPI_NP_FLAG" 1 "$RATE_BIN" --sync="$SYNC" -- config.yaml) > "$OUT/codes.out" 2>&1
