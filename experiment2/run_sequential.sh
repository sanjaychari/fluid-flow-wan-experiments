#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
# Load first: mpirun must never inherit cases.csv as the loop's stdin.
mapfile -t rows < "$ROOT/cases.csv"
for row in "${rows[@]}"; do
    row="${row%$'\r'}"
    IFS=, read -r case scenario seed workload config topology trace <<< "$row"
    [[ "$case" == case || -z "$case" ]] && continue
    "$ROOT/run_case.sh" "$case" 1 1
done
python3 "$ROOT/analyze.py"
