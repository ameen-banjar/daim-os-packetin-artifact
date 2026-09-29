#!/usr/bin/env python3
"""Reproduce the point-estimate means reported for the independent
clean-VM rerun (stage2_full_compare_independent_rerun_raw.csv,
INDEPENDENT_CLEAN_RERUN_REPORT.md). Deliberately no bootstrap: the
manuscript and the report present this rerun as a plain qualitative
replication check (does the ordering hold?), not an inferential claim,
so no confidence interval is published for it and none is computed here.
This script exists so that absence of a bootstrap script is not also
absence of any documented, re-executable way to regenerate the published
means from the raw data."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/stage2_full_compare_independent_rerun_raw.csv"
OUT = ROOT / "results/paper1"
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
SIZES = [8, 64]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))

    summary = []
    for size in SIZES:
        for mode in MODES:
            values = [
                float(row["install_mean_us"]) / 1000.0
                for row in raw
                if int(row["network_size"]) == size and row["mode"] == mode
            ]
            summary.append({
                "network_size": size,
                "mode": mode,
                "n": len(values),
                "mean_ms": sum(values) / len(values) if values else None,
            })

    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "note": (
            "Point estimates only, no bootstrap -- this rerun is reported as a "
            "qualitative replication check (does the mean ordering hold?), not "
            "an inferential claim; see INDEPENDENT_CLEAN_RERUN_REPORT.md."
        ),
        "summary": summary,
    }
    stats_path = OUT / "stage2_full_compare_independent_rerun_statistics.json"
    stats_path.write_text(json.dumps(result, indent=2) + "\n")
    print(stats_path)


if __name__ == "__main__":
    main()
