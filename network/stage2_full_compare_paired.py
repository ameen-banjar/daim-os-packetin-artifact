#!/usr/bin/env python3
"""Randomised-order, higher-repetition, paired extension of
stage2_full_compare.py, addressing the internal-validity threat the
manuscript records for that experiment: "matched adapter-overhead modes
were run sequentially rather than randomised... increasing its
repetitions beyond five... remain[s] future work for that specific
experiment" (Section 8).

Reuses stage2_full_compare.py's exact trial-execution functions
(run_cli_mode, run_direct_osken) unchanged -- same topology, same flow,
same per-switch install mechanics -- and changes only the orchestration:

  - 30 repetitions per (mode, size) instead of 5.
  - For each (size, repetition) pair, the four modes' trials are drawn in
    a freshly shuffled order (seeded, reproducible), so mode is never
    confounded with a fixed run-order position the way the original
    mode-major loop order was.
  - Because every mode's trial for a given (size, repetition) is run
    back-to-back in the same short window, repetition index is a valid
    pairing key: stage2_full_compare_paired_analysis.py computes paired
    differences (e.g. persistent[k] - process_per_rule[k] at a fixed
    size, for k=1..30) instead of treating each mode's 30 samples as
    independent groups, which better isolates the mode effect from
    slower host-load drift across the run than an unpaired comparison
    would.
"""
import csv
import random
import time
from pathlib import Path

from mininet.log import setLogLevel

from stage2_full_compare import (
    PERSISTENT_BASE_PORT,
    SIZES,
    ROOT,
    run_cli_mode,
    run_direct_osken,
)

RAW = ROOT / "results/network/stage2_full_compare_paired_raw.csv"
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
REPETITIONS = 30
SEED = 20260720


def run_trial(mode, size, repetition):
    if mode == "direct_osken":
        return run_direct_osken(size, repetition)
    return run_cli_mode(mode, size, repetition)


def main():
    setLogLevel("warning")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    rows = []
    trial_index = 0
    total = len(SIZES) * REPETITIONS * len(MODES)
    start = time.monotonic()
    for repetition in range(1, REPETITIONS + 1):
        for size in SIZES:
            block = list(MODES)
            rng.shuffle(block)
            for block_position, mode in enumerate(block, start=1):
                trial_index += 1
                elapsed_min = (time.monotonic() - start) / 60.0
                print(
                    f"trial {trial_index}/{total} "
                    f"(rep={repetition} size={size} mode={mode} "
                    f"block_position={block_position}/4, {elapsed_min:.1f} min elapsed)",
                    flush=True,
                )
                row = run_trial(mode, size, repetition)
                row["trial_index"] = trial_index
                row["block_position"] = block_position
                rows.append(row)
                with RAW.open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {RAW}")


if __name__ == "__main__":
    main()
