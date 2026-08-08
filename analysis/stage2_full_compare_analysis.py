#!/usr/bin/env python3
"""Statistics and figure for the four-way Stage-2 comparison
(stage2_full_compare_raw.csv): daim_process_per_rule, daim_persistent,
direct_ovs_cli, direct_osken. Mirrors paper1_analysis.py's bootstrap
methodology so the two are directly comparable."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/stage2_full_compare_raw.csv"
OUT = ROOT / "results/paper1"
SEED = 20260719
BOOTSTRAPS = 20000
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
SIZES = [8, 16, 32, 64]
LABELS = {
    "daim_process_per_rule": "DAIM (process-per-rule)",
    "daim_persistent": "DAIM (persistent adapter)",
    "direct_ovs_cli": "Direct ovs-ofctl (CLI)",
    "direct_osken": "Direct Os-Ken (no DAIM)",
}
COLORS = {
    "daim_process_per_rule": "#C45A24",
    "daim_persistent": "#2457A6",
    "direct_ovs_cli": "#8A8A8A",
    "direct_osken": "#2E7D32",
}


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def draw_chart(summary, path):
    width, height = 1600, 1000
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    small = ImageFont.load_default(size=31)
    left, top, right, bottom = 140, 80, 1500, 800
    draw.line((left, top, left, bottom), fill="#222222", width=3)
    draw.line((left, bottom, right, bottom), fill="#222222", width=3)
    ymax = 20.0
    for tick in range(0, 21, 4):
        y = bottom - (tick / ymax) * (bottom - top)
        draw.line((left - 8, y, right, y), fill="#dddddd", width=1)
        draw.text((45, y - 12), str(tick), fill="#222222", font=small)

    def y_of(v):
        return bottom - (v / ymax) * (bottom - top)

    offsets = {"daim_process_per_rule": -18, "daim_persistent": -6, "direct_ovs_cli": 6, "direct_osken": 18}
    for mode in MODES:
        points = []
        for idx, size in enumerate(SIZES):
            row = next(r for r in summary if r["network_size"] == size and r["mode"] == mode)
            x = left + idx * (right - left) / (len(SIZES) - 1) + offsets[mode]
            y = y_of(row["mean_ms"])
            points.append((x, y))
            lo, hi = row["bootstrap_95_ci_ms"]
            draw.line((x, y_of(lo), x, y_of(hi)), fill=COLORS[mode], width=2)
        draw.line(points, fill=COLORS[mode], width=5)
        for x, y in points:
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=COLORS[mode])

    for idx, size in enumerate(SIZES):
        x = left + idx * (right - left) / (len(SIZES) - 1)
        draw.text((x - 18, bottom + 18), str(size), fill="#222222", font=font)
    draw.text((580, 850), "Number of OVS switches", fill="#222222", font=font)
    draw.text((20, 20), "Mean per-switch install/confirm time (ms), whiskers = bootstrap 95% CI", fill="#111111", font=font)

    ly = 95
    for mode in MODES:
        draw.rectangle((1180, ly, 1210, ly + 22), fill=COLORS[mode])
        draw.text((1220, ly), LABELS[mode], fill="#222222", font=small)
        ly += 34

    draw.text((20, 900), "daim_persistent and direct_osken each require a connection already, or newly, established per switch in this workload;", fill="#555555", font=small)
    draw.text((20, 925), "their advantage over the process-per-rule/CLI paths narrows as switch count grows (see report for the exact figures).", fill="#555555", font=small)
    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)
    summary = []
    comparisons = []
    for size in SIZES:
        by_mode = {}
        for mode in MODES:
            values = [
                float(row["install_mean_us"]) / 1000.0
                for row in raw
                if int(row["network_size"]) == size and row["mode"] == mode
            ]
            by_mode[mode] = values
            summary.append({
                "network_size": size,
                "mode": mode,
                "n": len(values),
                "mean_ms": float(np.mean(values)),
                "sd_ms": float(np.std(values, ddof=1)),
                "median_ms": float(np.median(values)),
                "bootstrap_95_ci_ms": bootstrap_ci(values, rng),
                "connectivity_passes": sum(
                    int(row["ping_success"]) for row in raw
                    if int(row["network_size"]) == size and row["mode"] == mode
                ),
            })
        comparisons.append({
            "network_size": size,
            "daim_persistent_vs_process_per_rule_ratio": float(
                np.mean(by_mode["daim_persistent"]) / np.mean(by_mode["daim_process_per_rule"])
            ),
            "daim_persistent_vs_direct_osken_ratio": float(
                np.mean(by_mode["daim_persistent"]) / np.mean(by_mode["direct_osken"])
            ),
        })
    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "summary": summary,
        "comparisons": comparisons,
        "interpretation": (
            "Four-way isolation of process-spawn cost, DAIM Core/ctypes cost, "
            "and native-controller OpenFlow cost, extending the original "
            "DAIM-vs-direct-ovs-ofctl microbenchmark per external review "
            "feedback. Not a flow-setup-latency or new-flow-arrival benchmark."
        ),
    }
    (OUT / "stage2_full_compare_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(summary, OUT / "stage2_full_compare.png")
    print(OUT / "stage2_full_compare_statistics.json")
    print(OUT / "stage2_full_compare.png")


if __name__ == "__main__":
    main()
