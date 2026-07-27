#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
REPEATS="${REPEATS:-5}"
RUN_DIAGNOSTICS="${RUN_DIAGNOSTICS:-1}"
[[ -f "$ROOT/pairs.csv" ]] || "$ROOT/setup.sh"
require_file "$ZMQ_SERVER"; require_file "$ZMQ_CTL"
mkdir -p "$ROOT/results/server"

server_pid=""

# zmqmlctl uses a blocking ZeroMQ receive.  Never call status/exit without
# a wall-clock timeout, because an absent or dead server would otherwise
# block this experiment script indefinitely.
server_status() {
    timeout 2s python3 "$ZMQ_CTL" \
        --endpoint "$ZMQ_CLIENT_ENDPOINT" \
        --family fluid-flow-wan \
        --backend statistical \
        status
}

server_exit() {
    timeout 2s python3 "$ZMQ_CTL" \
        --endpoint "$ZMQ_CLIENT_ENDPOINT" \
        --family fluid-flow-wan \
        --backend statistical \
        exit
}

stop_server() {
    if [[ -n "$server_pid" ]]; then
        server_exit >/dev/null 2>&1 || true
        kill "$server_pid" >/dev/null 2>&1 || true
        wait "$server_pid" >/dev/null 2>&1 || true
    fi
}
trap stop_server EXIT

echo "[E3] Checking for an existing ZeroMQ server at $ZMQ_CLIENT_ENDPOINT"

if server_status >/dev/null 2>&1; then
    echo "a ZeroMQ server is already responding at $ZMQ_CLIENT_ENDPOINT; stop it before run_all.sh so this run owns the server lifecycle" >&2
    exit 1
fi

echo "[E3] Starting ZeroMQ statistical backend"

rm -f "$ROOT/results/server/zmqmlserver.log"
ZMQML_ENDPOINT="$ZMQ_SERVER_ENDPOINT" python3 "$ZMQ_SERVER" \
    > "$ROOT/results/server/zmqmlserver.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 50); do
    # Fail immediately if the server process itself died.
    if ! kill -0 "$server_pid" >/dev/null 2>&1; then
        echo "ZeroMQ server exited during startup" >&2
        echo "--- zmqmlserver.log ---" >&2
        cat "$ROOT/results/server/zmqmlserver.log" >&2
        exit 1
    fi

    if server_status > "$ROOT/results/server/status.txt" 2>/dev/null; then
        ready=1
        break
    fi

    sleep 0.2
done

if [[ "$ready" != 1 ]]; then
    echo "ZeroMQ server did not become ready within the startup timeout" >&2
    echo "--- zmqmlserver.log ---" >&2
    cat "$ROOT/results/server/zmqmlserver.log" >&2
    exit 1
fi

echo "[E3] ZeroMQ server ready"

# Materialize pair rows before mpirun so MPI cannot consume loop input.
mapfile -t rows < "$ROOT/pairs.csv"
for row in "${rows[@]}"; do
    row="${row%$'\r'}"
    IFS=, read -r switches load pdes stat <<< "$row"
    [[ "$switches" == switches || -z "$switches" ]] && continue
    echo "==== E3 scale=$switches load=$load ===="
    "$ROOT/run_case.sh" "$pdes" warmup performance
    "$ROOT/run_case.sh" "$stat" warmup performance
    for rep in $(seq 1 "$REPEATS"); do
        "$ROOT/run_case.sh" "$pdes" "$rep" performance
        "$ROOT/run_case.sh" "$stat" "$rep" performance
    done
    "$ROOT/check_parity.sh" "$pdes" "$stat"
    if [[ "$RUN_DIAGNOSTICS" == 1 ]]; then
        "$ROOT/run_case.sh" "$stat" 1 diagnostic
    fi
done
python3 "$ROOT/analyze.py"
