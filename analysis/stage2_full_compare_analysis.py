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
    "daim_process_per_rule": "DAIM process/rule",
    "daim_persistent": "DAIM persistent",
    "direct_ovs_cli": "Direct ovs-ofctl (CLI)",
    "direct_osken": "Direct Os-Ken",
}
MARKERS = {"daim_process_per_rule":"circle","daim_persistent":"square","direct_ovs_cli":"triangle","direct_osken":"diamond"}
LINE_STYLES = {"daim_process_per_rule":"solid","daim_persistent":"dashed","direct_ovs_cli":"dotted","direct_osken":"dashdot"}
COLORS = {"daim_process_per_rule":"#0072B2","daim_persistent":"#D55E00","direct_ovs_cli":"#009E73","direct_osken":"#7A5195"}


def styled_segment(draw, a, b, style, width=4, color="#111111"):
    x0, y0 = a; x1, y1 = b
    length = max(1.0, ((x1-x0)**2 + (y1-y0)**2)**0.5)
    patterns = {"solid": [length], "dashed": [28, 14], "dotted": [5, 12], "dashdot": [28, 10, 5, 10]}
    pattern = patterns[style]
    pos = 0.0; pi = 0; draw_on = True
    while pos < length:
        end = min(length, pos + pattern[pi % len(pattern)])
        if draw_on:
            xa=x0+(x1-x0)*pos/length; ya=y0+(y1-y0)*pos/length
            xb=x0+(x1-x0)*end/length; yb=y0+(y1-y0)*end/length
            draw.line((xa,ya,xb,yb), fill=color, width=width)
        pos=end; pi+=1; draw_on=not draw_on


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def draw_chart(summary, path):
    width, height = 1800, 940
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    small = ImageFont.load_default(size=39)
    left, top, right, bottom = 140, 100, 1330, 760
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
        for a, b in zip(points, points[1:]):
            styled_segment(draw, a, b, LINE_STYLES[mode], color=COLORS[mode])
        for x, y in points:
            shape=MARKERS[mode]
            if shape=="circle": draw.ellipse((x-8,y-8,x+8,y+8),fill=COLORS[mode])
            elif shape=="square": draw.rectangle((x-8,y-8,x+8,y+8),outline=COLORS[mode],width=4,fill="white")
            elif shape=="triangle": draw.polygon([(x,y-9),(x-9,y+8),(x+9,y+8)],outline=COLORS[mode],fill="white")
            else: draw.polygon([(x,y-9),(x+9,y),(x,y+9),(x-9,y)],outline=COLORS[mode],fill="white")

    for idx, size in enumerate(SIZES):
        x = left + idx * (right - left) / (len(SIZES) - 1)
        draw.text((x - 18, bottom + 18), str(size), fill="#222222", font=font)
    draw.text((520, 850), "Number of OVS switches", fill="#222222", font=font)
    draw.text((20, 20), "Mean per-switch install/confirm time (ms), whiskers = bootstrap 95% CI", fill="#111111", font=font)

    ly = 150
    for mode in MODES:
        x, y = 1406, ly + 14
        styled_segment(draw, (1378,y), (1434,y), LINE_STYLES[mode], 5, COLORS[mode])
        shape = MARKERS[mode]
        if shape == "circle": draw.ellipse((x-8,y-8,x+8,y+8),fill=COLORS[mode])
        elif shape == "square": draw.rectangle((x-8,y-8,x+8,y+8),outline=COLORS[mode],width=3,fill="white")
        elif shape == "triangle": draw.polygon([(x,y-9),(x-9,y+8),(x+9,y+8)],outline=COLORS[mode],fill="white")
        else: draw.polygon([(x,y-9),(x+9,y),(x,y+9),(x-9,y)],outline=COLORS[mode],fill="white")
        draw.text((1450, ly - 8), LABELS[mode], fill="#111111", font=small)
        ly += 66

    draw.text((1390, 440), "One rule/switch.", fill="#444444", font=small)
    draw.text((1390, 490), "Connection setup", fill="#444444", font=small)
    draw.text((1390, 540), "cost included.", fill="#444444", font=small)
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
                "p95_ms": float(np.percentile(values, 95)),
                "p99_ms": float(np.percentile(values, 99)),
                "max_ms": float(np.max(values)),
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
            "Four-way comparison of process-spawn cost, DAIM CLI-adapter wrapper cost (no DAIM Core or ctypes in any path), "
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
