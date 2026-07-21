#!/usr/bin/env python3
"""Does the 64-switch install-time tail (STAGE2_FULL_COMPARE_PAIRED_REPORT.md)
correlate with host CPU load? 120 real trials (30 reps x 4 modes,
randomised order, size=64 only) each recorded /proc/loadavg immediately
before and after the trial alongside install time. This computes the
Pearson correlation between install time and load (before), reports
whether the identified tail trials (install time > 2x that mode's own
median, the same threshold used in STAGE2_FULL_COMPARE_PAIRED_REPORT.md)
have systematically higher load than non-tail trials, and draws a
scatter plot."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/stage2_host_load_diagnostic_raw.csv"
OUT = ROOT / "results/paper1"
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
MODE_COLORS = {
    "daim_process_per_rule": "#C45A24",
    "daim_persistent": "#2457A6",
    "direct_ovs_cli": "#6BA292",
    "direct_osken": "#8A8A8A",
}


def pearson_r(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.corrcoef(x, y)[0, 1])


def draw_scatter(rows, path):
    width, height = 1100, 620
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=15)
    left, top, right, bottom = 110, 50, 1040, 480
    draw.line((left, top, left, bottom), fill="#222222", width=2)
    draw.line((left, bottom, right, bottom), fill="#222222", width=2)

    xs = [float(r["loadavg_1min_before"]) for r in rows]
    ys = [float(r["install_mean_us"]) / 1000.0 for r in rows]
    xmax = max(xs) * 1.1 or 1.0
    ymax = max(ys) * 1.1

    def px(v):
        return left + (v / xmax) * (right - left)

    def py(v):
        return bottom - (v / ymax) * (bottom - top)

    for r in rows:
        x = float(r["loadavg_1min_before"])
        y = float(r["install_mean_us"]) / 1000.0
        color = MODE_COLORS[r["mode"]]
        draw.ellipse((px(x) - 4, py(y) - 4, px(x) + 4, py(y) + 4), outline=color, width=2)

    for i in range(6):
        v = xmax * i / 5
        x = px(v)
        draw.line((x, bottom, x, bottom + 6), fill="#222222", width=1)
        draw.text((x - 12, bottom + 10), f"{v:.1f}", fill="#222222", font=small)
    for i in range(6):
        v = ymax * i / 5
        y = py(v)
        draw.line((left - 6, y, left, y), fill="#222222", width=1)
        draw.text((left - 55, y - 8), f"{v:.1f}", fill="#222222", font=small)

    draw.text((left, bottom + 40), "1-min load average immediately before trial", fill="#222222", font=font)
    draw.text((10, top - 30), "Install time (ms)", fill="#222222", font=font)

    ly = top
    for i, m in enumerate(MODES):
        cy = ly + i * 24
        draw.ellipse((right - 220, cy, right - 220 + 14, cy + 14), outline=MODE_COLORS[m], width=2)
        draw.text((right - 198, cy - 2), m, fill="#222222", font=small)

    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    overall_r = pearson_r(
        [r["loadavg_1min_before"] for r in rows],
        [r["install_mean_us"] for r in rows],
    )

    per_mode = {}
    for mode in MODES:
        mrows = [r for r in rows if r["mode"] == mode]
        install = [float(r["install_mean_us"]) for r in mrows]
        load_before = [float(r["loadavg_1min_before"]) for r in mrows]
        median = float(np.median(install))
        tail = [r for r, v in zip(mrows, install) if v > 2 * median]
        non_tail = [r for r, v in zip(mrows, install) if v <= 2 * median]
        per_mode[mode] = {
            "n": len(mrows),
            "median_install_us": median,
            "pearson_r_install_vs_load_before": pearson_r(load_before, install),
            "n_tail_trials": len(tail),
            "tail_mean_load_before": float(np.mean([float(r["loadavg_1min_before"]) for r in tail])) if tail else None,
            "non_tail_mean_load_before": float(np.mean([float(r["loadavg_1min_before"]) for r in non_tail])) if non_tail else None,
            "tail_trial_indices": [int(r["trial_index"]) for r in tail],
        }

    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "n_trials": len(rows),
        "overall_pearson_r_install_vs_load_before": overall_r,
        "per_mode": per_mode,
        "interpretation": (
            "Pearson correlation between each trial's install time and the "
            "1-minute host load average sampled immediately before that "
            "trial started, plus a direct comparison of mean load before "
            "tail trials (install time > 2x that mode's own median, same "
            "threshold as STAGE2_FULL_COMPARE_PAIRED_REPORT.md) versus "
            "non-tail trials. A positive correlation and higher tail-trial "
            "load would support host load as a contributing cause; a weak "
            "or absent correlation would indicate the tail is not "
            "explained by 1-minute load average as measured here."
        ),
    }
    (OUT / "stage2_host_load_diagnostic_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_scatter(rows, OUT / "stage2_host_load_diagnostic.png")
    print(OUT / "stage2_host_load_diagnostic_statistics.json")
    print(OUT / "stage2_host_load_diagnostic.png")


if __name__ == "__main__":
    main()
