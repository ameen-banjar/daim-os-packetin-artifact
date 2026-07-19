#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/results/stage2_calibration" "$ROOT/logs"
make -C "$ROOT/implementation" clean check all | tee "$ROOT/logs/stage2_linux_build.log"
sudo python3 "$ROOT/network/stage2_benchmark.py" \
  --config "$ROOT/configs/stage2_calibration.json" \
  --output "$ROOT/results/stage2_calibration" \
  | tee "$ROOT/logs/stage2_calibration_run.log"
python3 -m json.tool "$ROOT/results/stage2_calibration/metadata.json" >/dev/null
echo stage2_calibration_verification=PASS

