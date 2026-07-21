#!/usr/bin/env python3
"""Host-load diagnostic for the heavy-tailed variance task #19 found at 64
switches (STAGE2_FULL_COMPARE_PAIRED_REPORT.md): does a trial's install
time correlate with contemporaneous host CPU load, or is the tail
unrelated to load as this artifact can observe it?

Reuses stage2_full_compare.py's trial-execution functions unchanged, at
network_size=64 only (where the tail was found), 30 repetitions per mode,
mode order freshly shuffled within each repetition block (same design as
stage2_full_compare_paired.py, restricted to one size). Each trial's
/proc/loadavg 1-minute average is sampled immediately before and
immediately after, alongside the existing install-time and CPU-time
fields, so a slow trial can be checked against whether the host was
demonstrably busier at that moment.
"""
import csv
import random
import time
from pathlib import Path

from mininet.log import setLogLevel

from stage2_full_compare import SIZES, ROOT, run_cli_mode, run_direct_osken

RAW = ROOT / "results/network/stage2_host_load_diagnostic_raw.csv"
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
REPETITIONS = 30
SIZE = 64
SEED = 20260720


def loadavg_1min():
    return float(Path("/proc/loadavg").read_text().split()[0])


def run_trial(mode, size, repetition):
    if mode == "direct_osken":
        return run_direct_osken(size, repetition)
    return run_cli_mode(mode, size, repetition)


def main():
    assert SIZE in SIZES
    setLogLevel("warning")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    rows = []
    trial_index = 0
    total = REPETITIONS * len(MODES)
    start = time.monotonic()
    for repetition in range(1, REPETITIONS + 1):
        block = list(MODES)
        rng.shuffle(block)
        for block_position, mode in enumerate(block, start=1):
            trial_index += 1
            elapsed_min = (time.monotonic() - start) / 60.0
            print(
                f"trial {trial_index}/{total} (rep={repetition} mode={mode} "
                f"block_position={block_position}/4, {elapsed_min:.1f} min elapsed)",
                flush=True,
            )
            load_before = loadavg_1min()
            t0 = time.monotonic()
            row = run_trial(mode, SIZE, repetition)
            wall_s = time.monotonic() - t0
            load_after = loadavg_1min()
            row["trial_index"] = trial_index
            row["block_position"] = block_position
            row["loadavg_1min_before"] = load_before
            row["loadavg_1min_after"] = load_after
            row["wall_clock_s"] = wall_s
            rows.append(row)
            with RAW.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {RAW}")


if __name__ == "__main__":
    main()
