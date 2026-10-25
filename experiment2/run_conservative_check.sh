#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; "$ROOT/setup.sh"
# Small deterministic parity subset; override CASES to expand.
CASES="${CASES:-load-medium-seed2001 incast-8-seed2001 victim-asymmetric}"
for c in $CASES; do "$ROOT/run_case.sh" "$c" 2; done
