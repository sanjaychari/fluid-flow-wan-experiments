#!/usr/bin/env bash
set -euo pipefail

E4="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$E4/results"

CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
CODES_EXE="$CODES_BUILD/src/model-net-fluid-flow-wan-trace-traffic"

SIMGRID_EXE="$E4/simgrid-flow-benchmark"

# Can override, e.g.:
#   SCALES=128 ./experiment4/run.sh
SCALES="${SCALES:-32 64 128}"
RUN_SCALE_SWEEP="${RUN_SCALE_SWEEP:-1}"

# Interval-sensitivity subset of Experiment 4.  This is intentionally kept at
# one topology scale so that it measures the temporal-granularity tradeoff
# without turning the experiment into a second full scale matrix.
RUN_INTERVAL_SWEEP="${RUN_INTERVAL_SWEEP:-1}"
INTERVAL_SWEEP_SCALE="${INTERVAL_SWEEP_SCALE:-128}"
INTERVAL_SWEEP_SECONDS="${INTERVAL_SWEEP_SECONDS:-1 10 60 3600}"
# By default run every interval in the sweep. This can be narrowed (for
# example to "60 3600") while the analyzer still reads the complete sweep above.
INTERVAL_SWEEP_RUN_SECONDS="${INTERVAL_SWEEP_RUN_SECONDS:-$INTERVAL_SWEEP_SECONDS}"
SWEEP_INITIAL_CALIBRATION_SECONDS="${SWEEP_INITIAL_CALIBRATION_SECONDS:-1000}"
SWEEP_CALIBRATION_STEP_SECONDS="${SWEEP_CALIBRATION_STEP_SECONDS:-500}"
SWEEP_MAX_CALIBRATION_SECONDS="${SWEEP_MAX_CALIBRATION_SECONDS:-4000}"
# A simulated-time calibration horizon can collapse to only a few intervals
# for coarse sweeps. Keep enough interval steps for multi-hop forwarding.
SWEEP_MIN_INITIAL_CALIBRATION_INTERVALS="${SWEEP_MIN_INITIAL_CALIBRATION_INTERVALS:-32}"
SWEEP_MIN_CALIBRATION_STEP_INTERVALS="${SWEEP_MIN_CALIBRATION_STEP_INTERVALS:-8}"
SWEEP_MIN_MAX_CALIBRATION_INTERVALS="${SWEEP_MIN_MAX_CALIBRATION_INTERVALS:-64}"

INITIAL_CALIBRATION_DRAIN="${INITIAL_CALIBRATION_DRAIN:-1000}"
CALIBRATION_STEP="${CALIBRATION_STEP:-500}"
MAX_CALIBRATION_DRAIN="${MAX_CALIBRATION_DRAIN:-4000}"

EXPECTED_GBIT=500

[[ -x "$CODES_EXE" ]] || {
    echo "missing CODES executable: $CODES_EXE" >&2
    exit 1
}

mkdir -p "$RESULTS"

echo -n "SimGrid version: "
/usr/bin/pkg-config --modversion simgrid 2>/dev/null || echo "unknown"

g++ -std=c++17 -O2 \
    "$E4/simgrid-flow-benchmark.cpp" \
    -o "$SIMGRID_EXE" \
    -lsimgrid


set_codes_drain()
{
    local conf="$1"
    local drain="$2"

    python3 - "$conf" "$drain" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
drain = int(sys.argv[2])

text = path.read_text()

new_text, count = re.subn(
    r"(?m)^(\s*num_drain_intervals:\s*)\d+\s*$",
    rf"\g<1>{drain}",
    text,
    count=1,
)

if count != 1:
    raise SystemExit(
        f"could not uniquely replace num_drain_intervals in {path}"
    )

path.write_text(new_text)
PY
}


validate_codes_output()
{
    local output="$1"
    local expected_terminals="$2"

    python3 - "$output" "$expected_terminals" "$EXPECTED_GBIT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
expected_terminals = int(sys.argv[2])
expected_gbit = float(sys.argv[3])

tol = 1e-5

terminals = []
switches = []

for line in path.read_text(errors="replace").splitlines():
    if line.startswith("fluid-flow-wan-terminal "):
        fields = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k] = v
        terminals.append(fields)

    elif line.startswith("fluid-flow-wan gid="):
        fields = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k] = v
        switches.append(fields)


errors = []

if len(terminals) != expected_terminals:
    errors.append(
        f"found {len(terminals)} terminal summaries; "
        f"expected {expected_terminals}"
    )

for t in terminals:
    tid = t.get("terminal", "?")

    generated = float(t.get("generated_gbit", "nan"))
    sent = float(t.get("sent_gbit", "nan"))
    backlog = float(t.get("source_backlog_gbit", "nan"))
    received = float(t.get("received_gbit", "nan"))

    if abs(generated - expected_gbit) > tol:
        errors.append(
            f"terminal {tid}: generated={generated}, "
            f"expected={expected_gbit}"
        )

    if abs(sent - expected_gbit) > tol:
        errors.append(
            f"terminal {tid}: sent={sent}, "
            f"expected={expected_gbit}"
        )

    if abs(backlog) > tol:
        errors.append(
            f"terminal {tid}: source_backlog={backlog}"
        )

    if abs(received - expected_gbit) > tol:
        errors.append(
            f"terminal {tid}: received={received}, "
            f"expected={expected_gbit}"
        )


for s in switches:
    sid = s.get("switch", "?")

    ready = float(s.get("ready_queue_gbit", "nan"))
    occupied = float(
        s.get("shared_buffer_occupied_gbit", "nan")
    )
    dropped = float(s.get("dropped_gbit", "nan"))

    if abs(ready) > tol:
        errors.append(
            f"switch {sid}: ready_queue_gbit={ready}"
        )

    if abs(occupied) > tol:
        errors.append(
            f"switch {sid}: "
            f"shared_buffer_occupied_gbit={occupied}"
        )

    if abs(dropped) > tol:
        errors.append(
            f"switch {sid}: dropped_gbit={dropped}"
        )


if errors:
    print(
        f"FAIL: {len(errors)} incomplete/nonempty conditions",
        file=sys.stderr,
    )
    for err in errors[:10]:
        print(f"  {err}", file=sys.stderr)
    if len(errors) > 10:
        print(
            f"  ... plus {len(errors) - 10} more",
            file=sys.stderr,
        )
    raise SystemExit(1)

print(
    f"PASS: {len(terminals)} terminals complete; "
    f"{len(switches)} switch queues empty"
)
PY
}


seconds_to_intervals()
{
    local seconds="$1"
    local interval="$2"

    python3 - "$seconds" "$interval" <<'PY'
import math
import sys

seconds = float(sys.argv[1])
interval = float(sys.argv[2])
if seconds <= 0 or interval <= 0:
    raise SystemExit("seconds and interval must be positive")
print(max(1, math.ceil(seconds / interval)))
PY
}


if [[ "$RUN_SCALE_SWEEP" != "0" ]]; then
for S in $SCALES; do
    CASE="$RESULTS/$S"
    TERMINALS=$((S * 2))

    echo
    echo "========================================"
    echo "Experiment 4B: $S switches / $TERMINALS terminals"
    echo "========================================"

    rm -rf "$CASE"
    mkdir -p "$CASE"

    python3 "$E4/generate_case.py" \
        --codes-root "$CODES_ROOT" \
        --case-dir "$CASE" \
        --switches "$S"

    #
    # Dynamically calibrate CODES drain horizon.
    #
    CAL_DRAIN="$INITIAL_CALIBRATION_DRAIN"

    while true; do
        if (( CAL_DRAIN > MAX_CALIBRATION_DRAIN )); then
            echo \
                "ERROR: $S-switch case did not drain by " \
                "$MAX_CALIBRATION_DRAIN intervals" >&2
            exit 1
        fi

        echo "[$S] CODES drain calibration: $CAL_DRAIN intervals"

        set_codes_drain \
            "$CASE/codes-correctness.yaml" \
            "$CAL_DRAIN"

        rm -f "$CASE/terminal-events.csv"

        (
            cd "$CODES_BUILD"

            mpirun -np 1 \
                "$CODES_EXE" \
                --sync=1 -- \
                "$CASE/codes-correctness.yaml"
        ) > "$CASE/codes-calibration.out" 2>&1

        if validate_codes_output \
            "$CASE/codes-calibration.out" \
            "$TERMINALS"
        then
            echo "[$S] calibration drained successfully"
            break
        fi

        echo \
            "[$S] calibration horizon too short; " \
            "extending by $CALIBRATION_STEP intervals"

        CAL_DRAIN=$((CAL_DRAIN + CALIBRATION_STEP))
    done

    #
    # Determine actual final receive interval after a COMPLETE calibration.
    #
    LAST_RECEIVE="$(
        python3 - "$CASE/terminal-events.csv" <<'PY'
import csv
import sys

last = -1

with open(sys.argv[1], newline="") as f:
    for row in csv.DictReader(f):
        if row["event"] == "receive":
            last = max(last, int(row["interval"]))

if last < 0:
    raise SystemExit("no destination receive events found")

print(last)
PY
    )"

    # Margin beyond the actual final destination receive.
    DRAIN=$((LAST_RECEIVE + 5))

    echo "[$S] final receive interval: $LAST_RECEIVE"
    echo "[$S] timed-run drain intervals: $DRAIN"

    #
    # Generate logging-free timed CODES configuration.
    #
    python3 "$E4/generate_case.py" \
        --codes-root "$CODES_ROOT" \
        --case-dir "$CASE" \
        --switches "$S" \
        --performance-drain "$DRAIN"

    for R in 1 2 3; do
        echo "[$S] CODES performance repeat $R/3"

        (
            cd "$CODES_BUILD"

            mpirun -np 1 \
                "$CODES_EXE" \
                --sync=1 -- \
                "$CASE/codes-performance.yaml"
        ) > "$CASE/codes-performance-$R.out" 2>&1

        #
        # Never accept a timed result unless the full workload drained.
        #
        validate_codes_output \
            "$CASE/codes-performance-$R.out" \
            "$TERMINALS"

        echo "[$S] SimGrid performance repeat $R/3"

        "$SIMGRID_EXE" \
            --cfg=network/model:CM02 \
            --cfg=network/TCP-gamma:0 \
            --cfg=network/weight-S:0 \
            --cfg=network/crosstraffic:0 \
            "$CASE/platform.xml" \
            "$CASE/traffic.csv" \
            /dev/null \
            --summary-only \
            > "$CASE/simgrid-performance-$R.out" 2>&1
    done
done
fi


if [[ "$RUN_INTERVAL_SWEEP" != "0" ]]; then
    S="$INTERVAL_SWEEP_SCALE"
    TERMINALS=$((S * 2))

    for INTERVAL in $INTERVAL_SWEEP_RUN_SECONDS; do
        CASE="$RESULTS/interval-sweep/$S/${INTERVAL}s"

        echo
        echo "========================================"
        echo "Experiment 4C: interval sweep"
        echo "$S switches / $TERMINALS terminals / ${INTERVAL}s interval"
        echo "========================================"

        rm -rf "$CASE"
        mkdir -p "$CASE"

        INITIAL_DRAIN="$(
            seconds_to_intervals \
                "$SWEEP_INITIAL_CALIBRATION_SECONDS" \
                "$INTERVAL"
        )"
        STEP_DRAIN="$(
            seconds_to_intervals \
                "$SWEEP_CALIBRATION_STEP_SECONDS" \
                "$INTERVAL"
        )"
        MAX_DRAIN="$(
            seconds_to_intervals \
                "$SWEEP_MAX_CALIBRATION_SECONDS" \
                "$INTERVAL"
        )"

        if (( INITIAL_DRAIN < SWEEP_MIN_INITIAL_CALIBRATION_INTERVALS )); then
            INITIAL_DRAIN="$SWEEP_MIN_INITIAL_CALIBRATION_INTERVALS"
        fi
        if (( STEP_DRAIN < SWEEP_MIN_CALIBRATION_STEP_INTERVALS )); then
            STEP_DRAIN="$SWEEP_MIN_CALIBRATION_STEP_INTERVALS"
        fi
        if (( MAX_DRAIN < SWEEP_MIN_MAX_CALIBRATION_INTERVALS )); then
            MAX_DRAIN="$SWEEP_MIN_MAX_CALIBRATION_INTERVALS"
        fi

        python3 "$E4/generate_case.py" \
            --codes-root "$CODES_ROOT" \
            --case-dir "$CASE" \
            --switches "$S" \
            --interval-seconds "$INTERVAL" \
            --pilot-drain "$INITIAL_DRAIN"

        CAL_DRAIN="$INITIAL_DRAIN"

        while true; do
            if (( CAL_DRAIN > MAX_DRAIN )); then
                echo \
                    "ERROR: ${INTERVAL}s interval case did not drain by " \
                    "$MAX_DRAIN calibration intervals" >&2
                exit 1
            fi

            echo \
                "[$S/${INTERVAL}s] CODES drain calibration: " \
                "$CAL_DRAIN intervals"

            set_codes_drain \
                "$CASE/codes-correctness.yaml" \
                "$CAL_DRAIN"

            rm -f "$CASE/terminal-events.csv"

            (
                cd "$CODES_BUILD"

                mpirun -np 1 \
                    "$CODES_EXE" \
                    --sync=1 -- \
                    "$CASE/codes-correctness.yaml"
            ) > "$CASE/codes-calibration.out" 2>&1

            if validate_codes_output \
                "$CASE/codes-calibration.out" \
                "$TERMINALS"
            then
                echo "[$S/${INTERVAL}s] calibration drained successfully"
                break
            fi

            CAL_DRAIN=$((CAL_DRAIN + STEP_DRAIN))
        done

        LAST_RECEIVE="$(
            python3 - "$CASE/terminal-events.csv" <<'PY'
import csv
import sys

last = -1
with open(sys.argv[1], newline="") as f:
    for row in csv.DictReader(f):
        if row["event"] == "receive":
            last = max(last, int(row["interval"]))

if last < 0:
    raise SystemExit("no destination receive events found")
print(last)
PY
        )"

        DRAIN=$((LAST_RECEIVE + 5))

        echo "[$S/${INTERVAL}s] final receive interval: $LAST_RECEIVE"
        echo "[$S/${INTERVAL}s] timed-run drain intervals: $DRAIN"

        python3 "$E4/generate_case.py" \
            --codes-root "$CODES_ROOT" \
            --case-dir "$CASE" \
            --switches "$S" \
            --interval-seconds "$INTERVAL" \
            --performance-drain "$DRAIN"

        for R in 1 2 3; do
            echo "[$S/${INTERVAL}s] CODES performance repeat $R/3"

            (
                cd "$CODES_BUILD"

                mpirun -np 1 \
                    "$CODES_EXE" \
                    --sync=1 -- \
                    "$CASE/codes-performance.yaml"
            ) > "$CASE/codes-performance-$R.out" 2>&1

            validate_codes_output \
                "$CASE/codes-performance-$R.out" \
                "$TERMINALS"

            echo "[$S/${INTERVAL}s] SimGrid performance repeat $R/3"

            "$SIMGRID_EXE" \
                --cfg=network/model:CM02 \
                --cfg=network/TCP-gamma:0 \
                --cfg=network/weight-S:0 \
                --cfg=network/crosstraffic:0 \
                "$CASE/platform.xml" \
                "$CASE/traffic.csv" \
                /dev/null \
                --summary-only \
                > "$CASE/simgrid-performance-$R.out" 2>&1
        done
    done

    python3 "$E4/analyze_interval_sweep.py" "$RESULTS" \
        --scale "$INTERVAL_SWEEP_SCALE" \
        --intervals $INTERVAL_SWEEP_SECONDS \
        | tee "$RESULTS/experiment4-interval-sweep-summary.csv"
fi

if [[ "$RUN_SCALE_SWEEP" != "0" ]]; then
    # analyze.py reads all completed 32/64/128 cases.
    python3 "$E4/analyze.py" "$RESULTS" \
        | tee "$RESULTS/experiment4-performance-summary.csv"
fi

python3 "$E4/sanitize_results.py" \
    --results "$RESULTS" \
    --codes-root "$CODES_ROOT" \
    --repo-root "$E4/.."
