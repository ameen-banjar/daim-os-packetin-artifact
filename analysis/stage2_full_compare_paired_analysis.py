#!/usr/bin/env python3
"""Statistics and figure for the randomised-order, paired extension of the
4-way adapter-overhead comparison (stage2_full_compare_paired_raw.csv).

Because each (size, repetition) block contains exactly one trial per mode
drawn from a randomly shuffled, back-to-back short window (see
stage2_full_compare_paired.py's docstring), repetition index is a valid
pairing key across modes. In addition to the usual per-mode descriptive
summary, this computes paired mean differences (persistent minus each of
the other three modes, at each size) by resampling repetition indices --
not each mode's values independently -- which correctly propagates the
within-block correlation (e.g. shared host load at that point in the run)
into the confidence interval, unlike treating the two modes as
independent samples."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/stage2_full_compare_paired_raw.csv"
OUT = ROOT / "results/paper1"
SEED = 20260720
BOOTSTRAPS = 20000
MODES = ["daim_process_per_rule", "daim_persistent", "direct_ovs_cli", "direct_osken"]
SIZES = [8, 16, 32, 64]
MODE_LABELS = {
    "daim_process_per_rule": "DAIM process-per-rule",
    "daim_persistent": "DAIM persistent",
    "direct_ovs_cli": "Direct ovs-ofctl",
    "direct_osken": "Direct Os-Ken (no DAIM)",
}
MODE_COLORS = {
    "daim_process_per_rule": "#C45A24",
    "daim_persistent": "#2457A6",
    "direct_ovs_cli": "#6BA292",
    "direct_osken": "#8A8A8A",
}
PAIRS = [
    ("daim_persistent", "daim_process_per_rule"),
    ("daim_persistent", "direct_ovs_cli"),
    ("daim_persistent", "direct_osken"),
]


def bootstrap_mean_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def bootstrap_median_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    medians = np.median(draws, axis=1)
    return [float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))]


def draw_chart(per_mode, paired, path):
    width, height = 1500, 1250
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    small = ImageFont.load_default(size=30)

    # Left panel: per-mode mean install time vs. size, with CI whiskers.
    left0, left1 = 120, 1380
    top, bottom = 70, 500
    draw.line((left0, top, left0, bottom), fill="#222222", width=2)
    draw.line((left0, bottom, left1, bottom), fill="#222222", width=2)
    ymax = max(per_mode[s][m]["bootstrap_95_ci_us"][1] for s in SIZES for m in MODES) * 1.1
    xs = {s: left0 + (i + 0.5) * (left1 - left0) / len(SIZES) for i, s in enumerate(SIZES)}

    def y_of(v):
        return bottom - (v / ymax) * (bottom - top)

    for m in MODES:
        pts = []
        for s in SIZES:
            v = per_mode[s][m]["mean_us"]
            ci = per_mode[s][m]["bootstrap_95_ci_us"]
            x = xs[s]
            pts.append((x, y_of(v)))
            draw.line((x, y_of(ci[0]), x, y_of(ci[1])), fill=MODE_COLORS[m], width=2)
        for a, b in zip(pts, pts[1:]):
            draw.line((*a, *b), fill=MODE_COLORS[m], width=3)
        for x, y in pts:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=MODE_COLORS[m])
    for s in SIZES:
        draw.text((xs[s] - 10, bottom + 8), str(s), fill="#222222", font=small)
    draw.text((left0, bottom + 30), "Switches (n); mean install time (us) with 95% CI", fill="#222222", font=font)
    for i, m in enumerate(MODES):
        cy = top + i * 22
        draw.rectangle((left0, cy, left0 + 16, cy + 12), fill=MODE_COLORS[m])
        draw.text((left0 + 22, cy - 2), MODE_LABELS[m], fill="#222222", font=small)

    # Lower panel: paired mean differences (persistent - other), forest-plot style.
    right0, right1 = 120, 1380
    top, bottom = 670, 1100
    all_diffs = [paired[s][f"{a}_minus_{b}"]["bootstrap_95_ci_us"] for s in SIZES for a, b in PAIRS]
    dmax = max(abs(v) for ci in all_diffs for v in ci) * 1.15

    def xd_of(v):
        return (right0 + right1) / 2 + (v / dmax) * 430

    draw.line((xd_of(0), top, xd_of(0), bottom), fill="#222222", width=2)
    row_h = (bottom - top) / (len(SIZES) * len(PAIRS))
    row = 0
    pair_colors = ["#2457A6", "#6BA292", "#8A8A8A"]
    for s in SIZES:
        for pi, (a, b) in enumerate(PAIRS):
            y = top + (row + 0.5) * row_h
            d = paired[s][f"{a}_minus_{b}"]
            ci = d["bootstrap_95_ci_us"]
            mean = d["mean_diff_us"]
            draw.line((xd_of(ci[0]), y, xd_of(ci[1]), y), fill=pair_colors[pi], width=3)
            draw.ellipse((xd_of(mean) - 3, y - 3, xd_of(mean) + 3, y + 3), fill=pair_colors[pi])
            if pi == 0:
                draw.text((right0, y - 7), f"n={s}", fill="#222222", font=small)
            row += 1
    draw.text((right0, bottom + 30), "Paired mean difference vs. persistent (us), 95% CI; 0 = no difference", fill="#222222", font=font)
    for i, (a, b) in enumerate(PAIRS):
        cy = top + i * 30
        draw.rectangle((right0 + 670, cy, right0 + 690, cy + 18), fill=pair_colors[i])
        draw.text((right0 + 700, cy - 4), f"persistent - {MODE_LABELS[b]}", fill="#222222", font=small)

    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)

    by_key = {}
    for r in rows:
        by_key[(r["mode"], int(r["network_size"]), int(r["repetition"]))] = float(r["install_mean_us"])
    n_reps = max(int(r["repetition"]) for r in rows)

    per_mode = {}
    for size in SIZES:
        per_mode[size] = {}
        for mode in MODES:
            vals = [by_key[(mode, size, rep)] for rep in range(1, n_reps + 1) if (mode, size, rep) in by_key]
            if not vals:
                continue
            per_mode[size][mode] = {
                "n": len(vals),
                "mean_us": float(np.mean(vals)),
                "sd_us": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "bootstrap_95_ci_us": bootstrap_mean_ci(vals, rng) if len(vals) > 1 else [vals[0], vals[0]],
                "median_us": float(np.median(vals)),
                "max_us": float(np.max(vals)),
                "n_gt_2x_median": int(sum(1 for v in vals if v > 2 * np.median(vals))),
            }

    paired = {}
    for size in SIZES:
        paired[size] = {}
        for a, b in PAIRS:
            diffs = [
                by_key[(a, size, rep)] - by_key[(b, size, rep)]
                for rep in range(1, n_reps + 1)
                if (a, size, rep) in by_key and (b, size, rep) in by_key
            ]
            if not diffs or size not in per_mode or a not in per_mode[size] or b not in per_mode[size]:
                continue
            paired[size][f"{a}_minus_{b}"] = {
                "n_pairs": len(diffs),
                "mean_diff_us": float(np.mean(diffs)),
                "bootstrap_95_ci_us": bootstrap_mean_ci(diffs, rng) if len(diffs) > 1 else [diffs[0], diffs[0]],
                "ratio_a_over_b": per_mode[size][a]["mean_us"] / per_mode[size][b]["mean_us"],
                "median_diff_us": float(np.median(diffs)),
                "bootstrap_95_ci_median_us": bootstrap_median_ci(diffs, rng) if len(diffs) > 1 else [diffs[0], diffs[0]],
                "median_ratio_a_over_b": per_mode[size][a]["median_us"] / per_mode[size][b]["median_us"],
            }

    ping_fail = sum(1 for r in rows if r["ping_success"] not in ("1", "True", "true"))

    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "repetitions_per_condition": n_reps,
        "total_trials": len(rows),
        "ping_failures": ping_fail,
        "per_mode": per_mode,
        "paired_vs_persistent": paired,
        "interpretation": (
            f"Randomised-order (mode order freshly shuffled within each "
            f"(size, repetition) block), {n_reps}-repetition extension of "
            "the original 5-repetition 4-way comparison, addressing the "
            "internal-validity threat recorded against that experiment "
            "(sequential mode order, only 5 repetitions). Paired "
            "differences resample repetition index rather than treating "
            "modes as independent samples, since each repetition's four "
            "modes were drawn from the same short time window."
        ),
    }
    (OUT / "stage2_full_compare_paired_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(OUT / "stage2_full_compare_paired_statistics.json")
    if all(m in per_mode.get(s, {}) for s in SIZES for m in MODES) and all(
        f"{a}_minus_{b}" in paired.get(s, {}) for s in SIZES for a, b in PAIRS
    ):
        draw_chart(per_mode, paired, OUT / "stage2_full_compare_paired.png")
        print(OUT / "stage2_full_compare_paired.png")
    else:
        print("incomplete data: skipping figure (run again once all trials have completed)")


if __name__ == "__main__":
    main()
