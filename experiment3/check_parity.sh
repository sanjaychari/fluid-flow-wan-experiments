#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -ne 2 ]]; then echo "usage: $0 PDES_CASE STATISTICAL_CASE" >&2; exit 2; fi
P="$1"; S="$2"
prow=$(awk -F, -v c="$P" 'NR>1 && $1==c {print; exit}' "$ROOT/cases.csv"); prow="${prow//$'\r'/}"
srow=$(awk -F, -v c="$S" 'NR>1 && $1==c {print; exit}' "$ROOT/cases.csv"); srow="${srow//$'\r'/}"
IFS=, read -r _ psw _ pload _ _ _ _ <<< "$prow"
IFS=, read -r _ ssw _ sload _ _ _ _ <<< "$srow"
[[ "$psw" == "$ssw" && "$pload" == "$sload" ]] || { echo "not a matched pair" >&2; exit 2; }
pdir="$ROOT/results/scale${psw}/$pload/pdes/repeat1/logs"
sdir="$ROOT/results/scale${ssw}/$sload/statistical/repeat1/logs"
out="$ROOT/analysis/parity/scale${psw}-$pload"; mkdir -p "$out"
for csv in terminal-events.csv switch-events.csv flowlet-events.csv; do
    python3 "$ROOT/../common/canonicalize_csv.py" "$pdir/$csv" "$out/pdes-$csv"
    python3 "$ROOT/../common/canonicalize_csv.py" "$sdir/$csv" "$out/statistical-$csv"
    diff -u "$out/pdes-$csv" "$out/statistical-$csv"
done
echo "PASS" > "$out/PASS.txt"
echo "PASS: exact canonicalized output parity scale=$psw load=$pload"
