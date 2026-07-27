#!/usr/bin/env bash
# Shared environment for the standalone Fluid-Flow WAN experiment repository.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
ROSS_ROOT="${ROSS_ROOT:-$HOME/ross}"
MPIEXEC="${MPIEXEC:-mpirun}"
MPI_NP_FLAG="${MPI_NP_FLAG:--np}"

RANDOM_BIN="${RANDOM_BIN:-$CODES_BUILD/src/model-net-fluid-flow-wan-random-traffic}"
TRACE_BIN="${TRACE_BIN:-$CODES_BUILD/src/model-net-fluid-flow-wan-trace-traffic}"
PACKET_BIN="${PACKET_BIN:-$CODES_BUILD/src/model-net-synthetic}"
TOPOLOGY_GENERATOR="${TOPOLOGY_GENERATOR:-$CODES_ROOT/src/network-workloads/generate-fluid-flow-wan-topology.py}"
ZMQ_SERVER="${ZMQ_SERVER:-$CODES_ROOT/src/surrogate/zmqml/zmqmlserver.py}"
ZMQ_CTL="${ZMQ_CTL:-$CODES_ROOT/src/surrogate/zmqml/zmqmlctl.py}"
ZMQ_CLIENT_ENDPOINT="${ZMQ_CLIENT_ENDPOINT:-tcp://localhost:5555}"
ZMQ_SERVER_ENDPOINT="${ZMQ_SERVER_ENDPOINT:-tcp://*:5555}"

require_file() {
    [[ -f "$1" ]] || { echo "missing file: $1" >&2; exit 1; }
}

require_executable() {
    [[ -x "$1" ]] || { echo "missing executable: $1" >&2; exit 1; }
}

sha256_or_empty() {
    if [[ -f "$1" ]]; then sha256sum "$1" | awk '{print $1}'; else printf ''; fi
}
