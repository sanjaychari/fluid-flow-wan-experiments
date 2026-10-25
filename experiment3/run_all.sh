#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
REPEATS="${REPEATS:-3}"

"$ROOT/setup.sh"

# Read cases.csv on fd 3 so child commands such as mpirun cannot consume the
# loop's CSV input. This is compatible with macOS Bash 3.2 and modern Linux.
while IFS= read -r row <&3; do
    row="${row%$'\r'}"
    IFS=, read -r point nmsg payload hosts target fcfg ftrace pcfg <<< "$row"
    [[ "$point" == point || -z "$point" ]] && continue

    "$ROOT/run_one.sh" "$point" fluid warmup
    "$ROOT/run_one.sh" "$point" packet warmup

    rep=1
    while (( rep <= REPEATS )); do
        "$ROOT/run_one.sh" "$point" fluid "$rep"
        "$ROOT/run_one.sh" "$point" packet "$rep"
        rep=$((rep + 1))
    done
done 3< "$ROOT/cases.csv"

python3 "$ROOT/analyze.py"
