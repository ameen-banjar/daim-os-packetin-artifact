#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/results/network" "$ROOT/logs"

make -C "$ROOT/implementation" clean check all | tee "$ROOT/logs/linux_implementation_build.log"
sudo python3 "$ROOT/network/two_switch_demo.py" | tee "$ROOT/results/network/two_switch_demo.json"

python3 - <<'PY' "$ROOT/results/network/two_switch_demo.json"
import json, sys
data=json.load(open(sys.argv[1]))
assert data['evidence_level']=='measured_emulation'
assert data['ping_success'] is True
assert len(data['flows'])==4
print('stage1_network_verification=PASS')
PY

