#!/usr/bin/env python3
"""Generates and freezes the block-randomised trial order for the R5
restart-recovery official sample BEFORE any data collection, per the
approved plan: 30 blocks, each containing both arms (persistent,
reactive_osken) in a randomised order within the block, seeded and saved
so the schedule cannot be altered mid-collection without it being
visible as a diff."""
import json
import random
from pathlib import Path

SEED = 20260929  # fresh, not reused from any other experiment in this paper
N_BLOCKS = 30
ARMS = ["persistent", "reactive_osken"]

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/network/r5_official_schedule.json"


def main():
    rng = random.Random(SEED)
    blocks = []
    for block_index in range(1, N_BLOCKS + 1):
        order = ARMS[:]
        rng.shuffle(order)
        blocks.append({"block": block_index, "order": order})
    schedule = {
        "seed": SEED,
        "n_blocks": N_BLOCKS,
        "arms": ARMS,
        "recover_window_s": 30,
        "note": "Randomised arm order within each block; the block itself always contains one trial of each arm.",
        "blocks": blocks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schedule, indent=2) + "\n")
    print(OUT)
    for b in blocks[:5]:
        print(b)
    print("...")


if __name__ == "__main__":
    main()
