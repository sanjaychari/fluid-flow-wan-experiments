#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"

REPEATS="${REPEATS:-3}"
PARALLEL_RANKS="${PARALLEL_RANKS:-2 4 8 16}"
SWITCHES="${SWITCHES:-512}"
FLOWS="${FLOWS:-4096}"

RESULTS="$ROOT/results"
WORKLOAD="$RESULTS/workload"

rm -rf "$RESULTS"
mkdir -p "$RESULTS"
require_executable "$RATE_BIN"

python3 "$ROOT/generate_case.py" \
    --case-dir "$WORKLOAD" \
    --switches "$SWITCHES" \
    --flows "$FLOWS"

printf 'mode,ranks,repeat,runtime_sec,net_events,summary_sha256\n' > "$RESULTS/runs.csv"

parse_ross_stat() {
    python3 - "$1" "$2" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(errors="replace")
kind = sys.argv[2]

patterns = {
    "runtime": r"Running Time\s*[:=]\s*([0-9.eE+-]+)",
    "events": r"Net Events Processed\s+([0-9]+)",
}
m = re.search(patterns[kind], text)
if not m:
    raise SystemExit(f"missing ROSS {kind} in {sys.argv[1]}")
print(m.group(1))
PY
}

canonical_summary_hash() {
    python3 - "$1" <<'PY'
import csv
import hashlib
import io
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

if not fields:
    raise SystemExit(f"empty flow summary: {path}")

rows.sort(key=lambda row: int(row["flow_id"]))
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
w.writeheader()
w.writerows(rows)
print(hashlib.sha256(buf.getvalue().encode()).hexdigest())
PY
}

run_one() {
    local mode="$1"
    local ranks="$2"
    local repeat="$3"
    local sync
    if [[ "$mode" == "sequential" ]]; then
        sync=1
    else
        sync=2
    fi

    local out="$RESULTS/$mode/ranks$ranks/repeat$repeat"
    rm -rf "$out"
    mkdir -p "$out"

    cp "$WORKLOAD/codes.yaml" "$out/codes.yaml"
    cp "$WORKLOAD/flows.csv" "$out/flows.csv"
    cp "$WORKLOAD/topology.yaml" "$out/topology.yaml"
    cp "$WORKLOAD/workload-metadata.csv" "$out/workload-metadata.csv"

    local cmd=("$MPIEXEC" "$MPI_NP_FLAG" "$ranks" "$RATE_BIN" "--sync=$sync" -- codes.yaml)

    echo "[E5] mode=$mode ranks=$ranks repeat=$repeat"

    set +e
    (
        cd "$out"
        "${cmd[@]}"
    ) > "$out/codes.out" 2>&1
    local rc=$?
    set -e

    if (( rc != 0 )); then
        tail -100 "$out/codes.out" >&2
        return "$rc"
    fi

    local summary="$out/rate-fluid-flow-summary.csv"
    require_file "$summary"

    local runtime events checksum
    runtime="$(parse_ross_stat "$out/codes.out" runtime)"
    events="$(parse_ross_stat "$out/codes.out" events)"
    checksum="$(canonical_summary_hash "$summary")"

    printf '%s,%s,%s,%s,%s,%s\n' \
        "$mode" "$ranks" "$repeat" "$runtime" "$events" "$checksum" \
        >> "$RESULTS/runs.csv"
}

for repeat in $(seq 1 "$REPEATS"); do
    run_one sequential 1 "$repeat"
done

for ranks in $PARALLEL_RANKS; do
    for repeat in $(seq 1 "$REPEATS"); do
        run_one conservative "$ranks" "$repeat"
    done
done

python3 "$ROOT/analyze.py" "$RESULTS"
