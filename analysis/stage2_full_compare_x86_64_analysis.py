#!/usr/bin/env python3
"""Cross-architecture comparison: the original ARM64 4-way benchmark
(stage2_full_compare_raw.csv, hardware-accelerated QEMU/hvf) against an
identical 80-run replication on a second, independently provisioned
x86-64 environment (stage2_full_compare_x86_64_raw.csv), run under QEMU's
software (TCG) emulation on the same physical ARM64 host, since no
physical x86-64 machine was available (task #20).

Absolute install times are not directly comparable between the two rows:
TCG emulation inflates per-syscall/per-process cost by roughly an order
of magnitude and unevenly across modes (calibration: 6.8x-17.8x observed
per mode at one switch count), so this analysis reports each
architecture's own per-mode-size means separately and, as the informative
comparison, the mode ratios within each architecture -- whether the same
architectural mechanism (subprocess-spawn avoidance, bare-controller
baseline) produces the same *direction* and roughly comparable *relative
magnitude* of effect on both."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ARM_RAW = ROOT / "results/network/stage2_full_compare_raw.csv"
X86_RAW = ROOT / "results/network/stage2_full_compare_x86_64_raw.csv"
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


def bootstrap_mean_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarise(path, rng):
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    out = {}
    for size in SIZES:
        out[size] = {}
        for mode in MODES:
            vals = [float(r["install_mean_us"]) for r in rows
                    if r["mode"] == mode and int(r["network_size"]) == size]
            out[size][mode] = {
                "n": len(vals),
                "mean_us": float(np.mean(vals)),
                "bootstrap_95_ci_us": bootstrap_mean_ci(vals, rng),
            }
    ping_fail = sum(1 for r in rows if r["ping_success"] not in ("1", "True", "true"))
    return out, len(rows), ping_fail


def draw_chart(arm, x86, path):
    width, height = 1500, 1250
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    small = ImageFont.load_default(size=30)

    for panel, (data, title) in enumerate([(arm, "ARM64 (hvf-accelerated)"), (x86, "x86-64 (TCG-emulated)")]):
        px0, px1 = 120, 1380
        top = 70 + panel * 560
        bottom = top + 430
        draw.line((px0, top, px0, bottom), fill="#222222", width=2)
        draw.line((px0, bottom, px1, bottom), fill="#222222", width=2)
        ymax = max(data[s][m]["bootstrap_95_ci_us"][1] for s in SIZES for m in MODES) * 1.1
        xs = {s: px0 + (i + 0.5) * (px1 - px0) / len(SIZES) for i, s in enumerate(SIZES)}

        def y_of(v, ymax=ymax):
            return bottom - (v / ymax) * (bottom - top)

        for m in MODES:
            pts = []
            for s in SIZES:
                v = data[s][m]["mean_us"]
                ci = data[s][m]["bootstrap_95_ci_us"]
                x = xs[s]
                pts.append((x, y_of(v)))
                draw.line((x, y_of(ci[0]), x, y_of(ci[1])), fill=MODE_COLORS[m], width=2)
            for a, b in zip(pts, pts[1:]):
                draw.line((*a, *b), fill=MODE_COLORS[m], width=3)
            for x, y in pts:
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=MODE_COLORS[m])
        for s in SIZES:
            draw.text((xs[s] - 10, bottom + 8), str(s), fill="#222222", font=small)
        draw.text((px0, top - 30), title, fill="#111111", font=font)
        draw.text((px0, bottom + 30), "Switches (n); mean install time (us, note differing y-scales)", fill="#222222", font=small)

    for i, m in enumerate(MODES):
        cy = height - 55
        cx = 80 + i * 350
        draw.rectangle((cx, cy, cx + 16, cy + 12), fill=MODE_COLORS[m])
        draw.text((cx + 22, cy - 2), MODE_LABELS[m], fill="#222222", font=small)

    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    arm, arm_n, arm_fail = summarise(ARM_RAW, rng)
    x86, x86_n, x86_fail = summarise(X86_RAW, rng)

    ratios = {}
    for size in SIZES:
        ratios[size] = {
            "arm64": {
                "persistent_over_process_per_rule": arm[size]["daim_persistent"]["mean_us"] / arm[size]["daim_process_per_rule"]["mean_us"],
                "persistent_over_direct_osken": arm[size]["daim_persistent"]["mean_us"] / arm[size]["direct_osken"]["mean_us"],
            },
            "x86_64": {
                "persistent_over_process_per_rule": x86[size]["daim_persistent"]["mean_us"] / x86[size]["daim_process_per_rule"]["mean_us"],
                "persistent_over_direct_osken": x86[size]["daim_persistent"]["mean_us"] / x86[size]["direct_osken"]["mean_us"],
            },
        }

    result = {
        "evidence_level": "measured_emulation",
        "arm64_source": str(ARM_RAW.relative_to(ROOT)),
        "x86_64_source": str(X86_RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "arm64_n_trials": arm_n,
        "arm64_ping_failures": arm_fail,
        "x86_64_n_trials": x86_n,
        "x86_64_ping_failures": x86_fail,
        "arm64_per_mode_size": arm,
        "x86_64_per_mode_size": x86,
        "mode_ratios_by_architecture": ratios,
        "interpretation": (
            "Absolute install times are not comparable across architectures "
            "here: x86-64 runs under QEMU TCG software emulation on the "
            "same ARM64 host (no physical x86-64 machine was available), "
            "inflating per-operation cost by roughly an order of magnitude "
            "and unevenly across modes. The informative comparison is "
            "whether each mode's relative ratio to the others replicates "
            "in direction and rough magnitude across architectures."
        ),
    }
    (OUT / "stage2_full_compare_x86_64_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(arm, x86, OUT / "stage2_full_compare_x86_64.png")
    print(OUT / "stage2_full_compare_x86_64_statistics.json")
    print(OUT / "stage2_full_compare_x86_64.png")


if __name__ == "__main__":
    main()
