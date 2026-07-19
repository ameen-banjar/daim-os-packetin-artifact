#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/results/stage2_final_local" "$ROOT/logs"
make -C "$ROOT/implementation" clean check all | tee "$ROOT/logs/stage2_final_linux_build.log"
sudo python3 "$ROOT/network/stage2_benchmark.py" \
  --config "$ROOT/configs/stage2_final_local.json" \
  --output "$ROOT/results/stage2_final_local" \
  | tee "$ROOT/logs/stage2_final_local_run.log"
python3 -m json.tool "$ROOT/results/stage2_final_local/metadata.json" >/dev/null
echo stage2_final_local_verification=PASS

