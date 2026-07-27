#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
require_file "$TOPOLOGY_GENERATOR"
mkdir -p "$ROOT/topologies" "$ROOT/configs"
for switches in 32 64 128; do
    python3 "$TOPOLOGY_GENERATOR" \
        --switches "$switches" --terminals-per-switch 2 \
        --avg-switch-degree 4.0 --reverse-link-probability 0.50 \
        --switch-link-min-mbps 10000 --switch-link-max-mbps 30000 \
        --terminal-link-min-mbps 100000 --terminal-link-max-mbps 100000 \
        --switch-buffer-min-mb 100000 --switch-buffer-max-mb 100000 \
        --seed 12345 --output "$ROOT/topologies/topology-${switches}switch.yaml"
done
python3 - "$ROOT/topologies"/*.yaml <<'PY'
from pathlib import Path
import sys
for name in sys.argv[1:]:
    p=Path(name); p.write_text(p.read_text().rstrip()+"\n")
PY
python3 "$ROOT/generate_inputs.py"
