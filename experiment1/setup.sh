#!/usr/bin/env bash
set -euo pipefail
E1="$(cd "$(dirname "$0")" && pwd)"
CODES_ROOT="${CODES_ROOT:-$HOME/codes}"
CODES_BUILD="${CODES_BUILD:-$CODES_ROOT/build}"
CODES_EXE="$CODES_BUILD/src/model-net-fluid-flow-wan-trace-traffic"
[[ -x "$CODES_EXE" ]] || { echo "missing CODES executable: $CODES_EXE" >&2; exit 1; }
command -v mpirun >/dev/null || { echo "mpirun not found" >&2; exit 1; }
command -v pkg-config >/dev/null || { echo "pkg-config not found" >&2; exit 1; }
pkg-config --exists simgrid || {
    echo "SimGrid pkg-config entry not found" >&2
    echo "macOS: brew install simgrid pkg-config" >&2
    echo "Ubuntu: sudo apt install libsimgrid-dev" >&2
    exit 1
}
mkdir -p "$E1/results" "$E1/analysis"
echo "Experiment 1 inputs ready."
echo "CODES:   $CODES_EXE"
echo "SimGrid: $(pkg-config --modversion simgrid)"
