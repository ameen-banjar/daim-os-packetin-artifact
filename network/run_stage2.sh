#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/results/network" "$ROOT/logs"
make -C "$ROOT/implementation" clean all | tee "$ROOT/logs/stage2_linux_build.log"
sudo python3 "$ROOT/network/benchmark_stage2.py" | tee "$ROOT/logs/stage2_benchmark.log"

