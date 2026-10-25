#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/../common/env.sh"
python3 "$ROOT/generate_dragonfly_fluid_topology.py" "$ROOT/topologies/fluid-dragonfly.yaml"
python3 "$ROOT/generate_inputs.py"
