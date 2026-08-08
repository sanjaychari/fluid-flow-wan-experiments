#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$ROOT/cases.csv" ]] || "$ROOT/setup.sh"

# Read cases.csv on fd 3 rather than stdin. This is portable to macOS Bash 3.2
# and prevents mpirun/run_case.sh from consuming the loop's CSV input.
while IFS= read -r row <&3; do
    row="${row%$'\r'}"
    IFS=, read -r case scenario seed workload config topology trace <<< "$row"
    [[ "$case" == case || -z "$case" ]] && continue
    "$ROOT/run_case.sh" "$case" 1 1
done 3< "$ROOT/cases.csv"

python3 "$ROOT/analyze.py"
