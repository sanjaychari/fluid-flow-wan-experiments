#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; source "$ROOT/../common/env.sh"
DENSITIES="${DENSITIES:-very_sparse sparse medium dense}"; REPEATS="${REPEATS:-3}"; RESULTS="$ROOT/results"
rm -rf "$RESULTS"; mkdir -p "$RESULTS"; require_executable "$RATE_BIN"
command -v pkg-config >/dev/null; pkg-config --exists simgrid
CFLAGS="$(pkg-config --cflags simgrid)"; LIBS="$(pkg-config --libs simgrid)"
if [[ "$(uname -s)" == Darwin ]] && command -v brew >/dev/null; then CFLAGS="$CFLAGS -I$(brew --prefix boost)/include"; fi
${CXX:-c++} -std=c++17 -O2 $CFLAGS "$ROOT/simgrid-flow-benchmark.cpp" -o "$ROOT/simgrid-flow-benchmark" $LIBS
printf 'flow_density,model,repeat,runtime_sec\n' > "$RESULTS/runtime.csv"

parse_codes_runtime() {
    python3 - "$1" <<'PY'
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text(errors='replace')
m = re.search(r"Running Time\s*[:=]\s*([0-9.eE+-]+)", text)
if not m:
    raise SystemExit(f"missing CODES Running Time in {sys.argv[1]}")
print(m.group(1))
PY
}

parse_simgrid_runtime() {
    python3 - "$1" <<'PY'
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text(errors='replace')
m = re.search(r"SIMGRID_WALL_RUNTIME_SEC=([0-9.eE+-]+)", text)
if not m:
    raise SystemExit(f"missing SimGrid engine runtime in {sys.argv[1]}")
print(m.group(1))
PY
}
for DENSITY in $DENSITIES; do
    CASE="$RESULTS/$DENSITY"
    python3 "$ROOT/generate_case.py" --case-dir "$CASE" --density "$DENSITY"
    for R in $(seq 1 "$REPEATS"); do
        COUT="$CASE/codes-$R.out"; SOUT="$CASE/simgrid-$R.out"
        (
            cd "$CASE"
            "$MPIEXEC" "$MPI_NP_FLAG" 1 "$RATE_BIN" --sync=1 -- codes.yaml
        ) > "$COUT" 2>&1
        cp "$CASE/rate-fluid-flow-summary.csv" "$CASE/rate-fluid-flow-summary-$R.csv"
        cruntime=$(parse_codes_runtime "$COUT")

        "$ROOT/simgrid-flow-benchmark" --cfg=network/model:raw "$CASE/platform.xml" "$CASE/traffic.csv" "$CASE/simgrid-fct-$R.csv" > "$SOUT" 2>&1
        sruntime=$(parse_simgrid_runtime "$SOUT")

        printf '%s,codes,%s,%s\n' "$DENSITY" "$R" "$cruntime" >> "$RESULTS/runtime.csv"
        printf '%s,simgrid,%s,%s\n' "$DENSITY" "$R" "$sruntime" >> "$RESULTS/runtime.csv"
    done
done
python3 "$ROOT/analyze.py" "$RESULTS"
