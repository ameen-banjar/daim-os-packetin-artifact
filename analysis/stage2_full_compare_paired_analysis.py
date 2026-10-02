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
    "daim_process_per_rule": "DAIM process/rule",
    "daim_persistent": "DAIM persistent",
    "direct_ovs_cli": "Direct ovs-ofctl",
    "direct_osken": "Direct Os-Ken",
}
LINE_STYLES = ["solid", "dashed", "dotted", "dashdot"]
MODE_COLORS = ["#0072B2", "#D55E00", "#009E73", "#7A5195"]
PAIRS = [
    ("daim_persistent", "daim_process_per_rule"),
    ("daim_persistent", "direct_ovs_cli"),
    ("daim_persistent", "direct_osken"),
]

def styled_segment(draw, a, b, style, width=3, color="#111111"):
    x0,y0=a; x1,y1=b
    length=max(1.0,((x1-x0)**2+(y1-y0)**2)**0.5)
    patterns={"solid":[length],"dashed":[24,12],"dotted":[4,10],"dashdot":[24,9,4,9]}
    pos=0.0; pi=0; on=True
    while pos<length:
        end=min(length,pos+patterns[style][pi%len(patterns[style])])
        if on:
            draw.line((x0+(x1-x0)*pos/length,y0+(y1-y0)*pos/length,x0+(x1-x0)*end/length,y0+(y1-y0)*end/length),fill=color,width=width)
        pos=end; pi+=1; on=not on


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
    """Two-panel figure (matplotlib; values in ms). Visual layout only --
    the plotted statistics are those in the statistics JSON."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def get(d, k):
        return d[k] if k in d else d[str(k)]

    markers = ["o", "s", "^", "D"]
    fills = [True, False, False, False]
    styles = ["-", "--", ":", "-."]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5.2), gridspec_kw={"width_ratios": [1, 1.05]})

    xs = list(range(len(SIZES)))
    for i, m in enumerate(MODES):
        means = [get(per_mode, s)[m]["mean_us"] / 1000 for s in SIZES]
        lo = [get(per_mode, s)[m]["bootstrap_95_ci_us"][0] / 1000 for s in SIZES]
        hi = [get(per_mode, s)[m]["bootstrap_95_ci_us"][1] / 1000 for s in SIZES]
        off = (i - 1.5) * 0.06
        ax1.errorbar([x + off for x in xs], means, yerr=[[a - l for a, l in zip(means, lo)], [h - a for a, h in zip(means, hi)]],
                     color=MODE_COLORS[i], linestyle=styles[i], marker=markers[i], markersize=7,
                     markerfacecolor=MODE_COLORS[i] if fills[i] else "white", capsize=3, linewidth=1.6,
                     label=MODE_LABELS[m])
    ax1.set_xticks(xs)
    ax1.set_xticklabels([str(s) for s in SIZES])
    ax1.set_xlabel("Number of OVS switches")
    ax1.set_ylabel("Mean per-switch install time (ms)")
    ax1.set_title("A. Per-mode mean, bootstrap 95% CI", loc="left", fontsize=12)
    ax1.set_ylim(bottom=0)
    ax1.grid(axis="y", alpha=0.2)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False, fontsize=9.5)

    ypos = []
    labels = []
    row = 0
    for si, s in enumerate(SIZES):
        for pi, (a, b) in enumerate(PAIRS):
            d = get(paired, s)[f"{a}_minus_{b}"]
            ci = [v / 1000 for v in d["bootstrap_95_ci_us"]]
            mean = d["mean_diff_us"] / 1000
            y = -(si * 4 + pi)
            ax2.plot(ci, [y, y], color=MODE_COLORS[pi], linestyle=styles[pi], linewidth=1.8)
            ax2.plot([mean], [y], marker=markers[pi], color=MODE_COLORS[pi], markersize=7,
                     markerfacecolor=MODE_COLORS[pi] if fills[pi] else "white")
        ypos.append(-(si * 4 + 1))
        labels.append(f"{s} switches")
    ax2.axvline(0, color="#222222", linewidth=1.2)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(labels)
    ax2.set_xlabel("Paired mean difference (ms), persistent minus comparison")
    ax2.set_title("B. Paired difference vs. persistent, 95% CI", loc="left", fontsize=12)
    ax2.grid(axis="x", alpha=0.2)
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], color=MODE_COLORS[i], linestyle=styles[i], marker=markers[i],
                      markerfacecolor=MODE_COLORS[i] if fills[i] else "white", label=f"persistent - {MODE_LABELS[b]}")
               for i, (a, b) in enumerate(PAIRS)]
    ax2.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=1, frameon=False, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


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
                "p95_us": float(np.percentile(vals, 95)),
                "p99_us": float(np.percentile(vals, 99)),
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
                "p95_diff_us": float(np.percentile(diffs, 95)),
                "p99_diff_us": float(np.percentile(diffs, 99)),
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
