#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CASE="${CASE:-load-medium-seed2001}"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"
row=$(awk -F, -v c="$CASE" 'NR>1 && $1==c {print; exit}' "$ROOT/cases.csv"); row="${row//$'\r'/}"
IFS=, read -r _ scenario seed _ _ _ _ <<< "$row"
"$ROOT/run_case.sh" "$CASE" 1 1
for np in 2 4; do
    "$ROOT/run_case.sh" "$CASE" 2 "$np"
    seq="$ROOT/results/$scenario/seed$seed/$CASE/sync1-np1/logs"
    con="$ROOT/results/$scenario/seed$seed/$CASE/sync2-np${np}/logs"
    cmpdir="$ROOT/analysis/conservative-parity/$CASE/np${np}"
    mkdir -p "$cmpdir"
    for csv in terminal-events.csv switch-events.csv flowlet-events.csv; do
        python3 "$ROOT/../common/canonicalize_csv.py" "$seq/$csv" "$cmpdir/sequential-$csv"
        python3 "$ROOT/../common/canonicalize_csv.py" "$con/$csv" "$cmpdir/conservative-$csv"
        diff -u "$cmpdir/sequential-$csv" "$cmpdir/conservative-$csv"
    done
    echo "PASS: $CASE sequential == conservative np=$np committed CSVs"
done
