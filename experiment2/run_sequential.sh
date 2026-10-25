#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
"$ROOT/setup.sh"

# Keep cases.csv on a dedicated file descriptor.  mpirun may read stdin, so a
# pipeline such as `tail ... | while read ...` can let the first MPI launch
# consume the remaining case rows.
while IFS= read -r row <&3; do
    row="${row%$'\r'}"
    IFS=, read -r name scenario seed cfg topo flow <<< "$row"
    [[ "$name" == case || -z "$name" ]] && continue
    "$ROOT/run_case.sh" "$name" 1
done 3< "$ROOT/cases.csv"

python3 "$ROOT/analyze.py"
