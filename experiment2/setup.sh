#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
require_file "$TOPOLOGY_GENERATOR"
mkdir -p "$ROOT/topologies" "$ROOT/configs" "$ROOT/traces"

for gb in 25 100 400; do
    mb=$((gb * 1000))
    python3 "$TOPOLOGY_GENERATOR" \
        --switches 64 \
        --terminals-per-switch 2 \
        --avg-switch-degree 4.0 \
        --reverse-link-probability 0.50 \
        --switch-link-min-mbps 10000 \
        --switch-link-max-mbps 30000 \
        --terminal-link-min-mbps 100000 \
        --terminal-link-max-mbps 100000 \
        --switch-buffer-min-mb "$mb" \
        --switch-buffer-max-mb "$mb" \
        --seed 12345 \
        --output "$ROOT/topologies/topology-buffer${gb}Gb.yaml"
done
python3 - "$ROOT/topologies"/*.yaml <<'PY'
from pathlib import Path
import sys
for name in sys.argv[1:]:
    p=Path(name); p.write_text(p.read_text().rstrip()+"\n")
PY

python3 "$ROOT/generate_trace_scenarios.py"
python3 "$ROOT/generate_inputs.py"
