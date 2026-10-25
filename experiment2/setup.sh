#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; source "$ROOT/../common/env.sh"; require_executable "$RATE_BIN"; python3 "$ROOT/generate_inputs.py"
