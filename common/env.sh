#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO_ROOT/common${PYTHONPATH:+:$PYTHONPATH}"
CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
ROSS_ROOT="${ROSS_ROOT:-$HOME/ross}"
MPIEXEC="${MPIEXEC:-mpirun}"
MPI_NP_FLAG="${MPI_NP_FLAG:--np}"
RATE_BIN="${RATE_BIN:-$CODES_BUILD/src/model-net-rate-fluid-wan}"
TRACE_BIN="${TRACE_BIN:-$RATE_BIN}"
PACKET_BIN="${PACKET_BIN:-$CODES_BUILD/src/model-net-synthetic}"
require_file() { [[ -f "$1" ]] || { echo "missing file: $1" >&2; exit 1; }; }
require_executable() { [[ -x "$1" ]] || { echo "missing executable: $1" >&2; exit 1; }; }
sha256_or_empty() { if [[ -f "$1" ]]; then shasum -a 256 "$1" | awk '{print $1}'; else printf ''; fi; }
