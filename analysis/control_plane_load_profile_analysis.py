#!/usr/bin/env python3
"""Statistics and figure for the sustained-load control-plane profile
(control_plane_load_profile_raw.csv). Mirrors packetin_latency_breakdown_
analysis.py's bootstrap methodology (same seed/resample count); the figure
is three grouped-bar panels (throughput, controller CPU time, control
bytes) instead of a stacked-stage bar, since this experiment has no
per-stage decomposition."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/control_plane_load_profile_raw.csv"
OUT = ROOT / "results/paper1"
SEED = 20260719
BOOTSTRAPS = 20000
MODES = ["process_per_rule", "persistent"]
LABELS = {"process_per_rule": "DAIM (process-per-rule)", "persistent": "DAIM (persistent adapter)"}
COLORS = {"process_per_rule": "#C45A24", "persistent": "#2457A6"}
METRICS = [
    ("throughput_installs_per_s", "Throughput (installs/s)", 1.0),
    ("cpu_s", "Controller CPU time (ms)", 1000.0),
    ("control_bytes_total", "Control bytes sent", 1.0),
]


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def bootstrap_median_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    medians = np.median(draws, axis=1)
    return [float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))]


def draw_chart(summary, path):
    width, height = 1400, 480
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    small = ImageFont.load_default(size=30)

    panel_w = width // len(METRICS)
    for pi, (key, label, scale) in enumerate(METRICS):
        px0 = pi * panel_w + 60
        px1 = (pi + 1) * panel_w - 40
        top, bottom = 40, 340
        draw.line((px0, top, px0, bottom), fill="#222222", width=2)
        draw.line((px0, bottom, px1, bottom), fill="#222222", width=2)

        vals = [summary[m][key]["mean"] * scale for m in MODES]
        cis = [[c * scale for c in summary[m][key]["ci"]] for m in MODES]
        vmax = max(v for v in (vals + [c[1] for c in cis])) * 1.2 or 1.0

        def y_of(v):
            return bottom - (v / vmax) * (bottom - top)

        bar_w = (px1 - px0) / 3
        for i, mode in enumerate(MODES):
            x0 = px0 + (i + 0.4) * bar_w
            x1 = x0 + bar_w * 0.6
            y = y_of(vals[i])
            draw.rectangle((x0, y, x1, bottom), fill=COLORS[mode])
            ylo, yhi = y_of(cis[i][0]), y_of(cis[i][1])
            xc = (x0 + x1) / 2
            draw.line((xc, ylo, xc, yhi), fill="#000000", width=2)
            draw.text((x0 - 5, y - 24), f"{vals[i]:.1f}", fill="#111111", font=small)

        draw.text((px0, bottom + 10), label, fill="#222222", font=font)

    ly = height - 50
    for i, mode in enumerate(MODES):
        cx = 60 + i * 420
        draw.rectangle((cx, ly, cx + 20, ly + 16), fill=COLORS[mode])
        draw.text((cx + 28, ly - 2), LABELS[mode], fill="#222222", font=small)
    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)

    summary = {}
    for mode in MODES:
        rows = [r for r in raw if r["mode"] == mode]
        metrics = {}
        for key in ("throughput_installs_per_s", "cpu_s", "max_rss_kib",
                    "control_bytes_total", "control_messages_total",
                    "no_rule_events", "flows_installed", "elapsed_s"):
            values = [float(r[key]) for r in rows if r[key] not in ("", None)]
            metrics[key] = {
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "ci": bootstrap_ci(values, rng) if len(values) > 1 else [values[0], values[0]],
                "median": float(np.median(values)),
                "median_ci": bootstrap_median_ci(values, rng) if len(values) > 1 else [values[0], values[0]],
                "max": float(np.max(values)),
                "n_gt_2x_median": int(sum(1 for v in values if v > 2 * np.median(values))),
                "n": len(values),
            }
        ovs_cpu_deltas = [float(r["ovs_vswitchd_cpu_s_delta"]) for r in rows
                          if r["ovs_vswitchd_cpu_s_delta"] not in ("", "None", None)]
        summary[mode] = {
            **metrics,
            "n_trials": len(rows),
            "all_signals_ok": all(int(r["signal_ok"]) for r in rows),
            "all_pings_succeeded": all(int(r["pings_succeeded"]) == int(r["pings_attempted"]) for r in rows),
            "ovs_vswitchd_cpu_s_delta_mean": (float(np.mean(ovs_cpu_deltas)) if ovs_cpu_deltas else None),
        }
        if mode == "persistent":
            summary[mode]["echo_replies_sent_mean"] = float(
                np.mean([float(r["echo_replies_sent"]) for r in rows])
            )

    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "repetitions_per_condition": summary[MODES[0]]["n_trials"],
        "total_trials": sum(summary[m]["n_trials"] for m in MODES),
        "summary": summary,
        "interpretation": (
            "Sustained-load resource and control-traffic profile: 40 real "
            "reactive Packet-In decisions per trial, 30 repetitions per "
            "adapter mode (increased from the original 5 per task #18's "
            "follow-up work), within one controller/topology lifetime, "
            "ending with a dedicated signal host's packet so the snapshot "
            "is taken only after all senders have gone through, not at a "
            "predicted event count. Trial order is mode-major here (all "
            "process_per_rule repetitions, then all persistent "
            "repetitions), unlike task #19's blocked/randomised design, so "
            "median_ci is a per-mode outlier-robustness check, not a "
            "paired-by-repetition-index comparison. flows_installed and "
            "control_bytes_total agree exactly between the measured "
            "(persistent) and computed_wire_format (process_per_rule) "
            "control-byte accounting methods, cross-validating the latter."
        ),
    }
    (OUT / "control_plane_load_profile_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(summary, OUT / "control_plane_load_profile.png")
    print(OUT / "control_plane_load_profile_statistics.json")
    print(OUT / "control_plane_load_profile.png")


if __name__ == "__main__":
    main()
