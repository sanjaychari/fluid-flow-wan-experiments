#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPEATS="${REPEATS:-3}"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
mapfile -t rows < "$ROOT/cases.csv"
for row in "${rows[@]}"; do
    row="${row%$'\r'}"
    IFS=, read -r point nmsg payload hosts target fcfg ftrace pcfg <<< "$row"
    [[ "$point" == point || -z "$point" ]] && continue
    "$ROOT/run_one.sh" "$point" fluid warmup
    "$ROOT/run_one.sh" "$point" packet warmup
    for rep in $(seq 1 "$REPEATS"); do
        "$ROOT/run_one.sh" "$point" fluid "$rep"
        "$ROOT/run_one.sh" "$point" packet "$rep"
    done
done
python3 "$ROOT/analyze.py"
