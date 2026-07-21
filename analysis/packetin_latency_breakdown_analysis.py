#!/usr/bin/env python3
"""Statistics and figure for the Packet-In stage-latency breakdown
(packetin_latency_breakdown_raw.csv). Mirrors stage2_full_compare_analysis.py's
bootstrap methodology; unlike that script there is no switch-count axis, so
the figure is a stacked bar per adapter mode instead of a line-per-size plot."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/packetin_latency_breakdown_raw.csv"
OUT = ROOT / "results/paper1"
SEED = 20260719
BOOTSTRAPS = 20000
MODES = ["process_per_rule", "persistent"]
LABELS = {"process_per_rule": "DAIM (process-per-rule)", "persistent": "DAIM (persistent adapter)"}
COLORS = {
    "dispatch": "#8A8A8A",
    "ctypes_in": "#C9A227",
    "decision": "#2457A6",
    "table_write": "#6BA292",
    "install_call": "#C45A24",
    "ctypes_out": "#C9A227",
    "packetout_send": "#8A8A8A",
    "confirm": "#8E3B46",
}
STAGES = ["dispatch", "ctypes_in", "decision", "table_write", "install_call",
          "ctypes_out", "packetout_send", "confirm"]
STAGE_LABELS = {
    "dispatch": "Os-Ken dispatch + bridge lookup",
    "ctypes_in": "ctypes crossing (in)",
    "decision": "Core decision (learn+lookup)",
    "table_write": "daim_table_write",
    "install_call": "OVS install call (flow_add)",
    "ctypes_out": "ctypes crossing (out)",
    "packetout_send": "PacketOut send",
    "confirm": "Switch-side confirmation (dump-flows)",
}


def stage_deltas_us(row):
    ns = {k: (None if v in ("", None) else int(v)) for k, v in row.items()
          if k.startswith(("t_", "c_"))}
    out = {
        "dispatch": ns["t_pre_ctypes_ns"] - ns["t_dispatch_enter_ns"],
        "ctypes_in": ns["c_entry_ns"] - ns["t_pre_ctypes_ns"],
        "decision": ns["c_decision_done_ns"] - ns["c_entry_ns"],
        "table_write": ns["c_table_write_done_ns"] - ns["c_decision_done_ns"],
        "install_call": ns["c_install_done_ns"] - ns["c_table_write_done_ns"],
        "ctypes_out": ns["t_post_ctypes_ns"] - ns["c_exit_ns"],
        "packetout_send": ns["t_packetout_sent_ns"] - ns["t_post_ctypes_ns"],
    }
    if ns["t_confirmed_ns"] is not None:
        out["confirm"] = ns["t_confirmed_ns"] - ns["t_packetout_sent_ns"]
        out["total"] = ns["t_confirmed_ns"] - ns["t_dispatch_enter_ns"]
    else:
        out["confirm"] = None
        out["total"] = None
    return {k: (v / 1000.0 if v is not None else None) for k, v in out.items()}


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def draw_chart(summary, path):
    width, height = 1400, 560
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=17)
    left, top, right, bottom = 220, 40, 1350, 380
    draw.line((left, top, left, bottom), fill="#222222", width=3)
    draw.line((left, bottom, right, bottom), fill="#222222", width=3)

    max_total = max(sum(s["mean_us"][st] for st in STAGES if s["mean_us"][st] is not None)
                     for s in summary)
    xmax = max_total * 1.15

    def x_of(v):
        return left + (v / xmax) * (right - left)

    bar_h = 90
    for idx, s in enumerate(summary):
        y0 = top + 20 + idx * 170
        cum = 0.0
        for st in STAGES:
            v = s["mean_us"][st]
            if v is None:
                continue
            x0, x1 = x_of(cum), x_of(cum + v)
            draw.rectangle((x0, y0, x1, y0 + bar_h), fill=COLORS[st])
            cum += v
        draw.text((10, y0 + bar_h / 2 - 10), LABELS[s["mode"]], fill="#111111", font=font)
        draw.text((left, y0 + bar_h + 6), f"total {cum / 1000.0:.3f} ms", fill="#333333", font=small)

    for tick_us in range(0, int(xmax) + 1, max(1, int(xmax) // 8 or 1)):
        x = x_of(tick_us)
        draw.line((x, top, x, bottom), fill="#eeeeee", width=1)
        draw.text((x - 14, bottom + 6), f"{tick_us / 1000.0:.1f}", fill="#222222", font=small)
    draw.text((left, bottom + 28), "Mean stage latency, stacked (ms)", fill="#222222", font=font)

    ly = bottom + 70
    col_x = [left, left + 620]
    for i, st in enumerate(STAGES):
        cx = col_x[i // 4]
        cy = ly + (i % 4) * 26
        draw.rectangle((cx, cy, cx + 20, cy + 16), fill=COLORS[st])
        draw.text((cx + 28, cy - 2), STAGE_LABELS[st], fill="#222222", font=small)
    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)

    summary = []
    for mode in MODES:
        mode_rows = [r for r in raw if r["mode"] == mode]
        deltas = [stage_deltas_us(r) for r in mode_rows]
        mean_us, ci_us, sd_us, n_by_stage = {}, {}, {}, {}
        for stage in STAGES + ["total"]:
            values = [d[stage] for d in deltas if d[stage] is not None]
            n_by_stage[stage] = len(values)
            if values:
                mean_us[stage] = float(np.mean(values))
                sd_us[stage] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
                ci_us[stage] = bootstrap_ci(values, rng) if len(values) > 1 else [mean_us[stage], mean_us[stage]]
            else:
                mean_us[stage] = None
                sd_us[stage] = None
                ci_us[stage] = None
        summary.append({
            "mode": mode,
            "n": len(mode_rows),
            "confirmed_n": n_by_stage["confirm"],
            "ping_success_n": sum(int(r["ping_success"]) for r in mode_rows),
            "priming_ok_n": sum(int(r["priming_ok"]) for r in mode_rows),
            "installed_n": sum(1 for r in mode_rows if r["installed"] in ("True", "1", "true")),
            "mean_us": mean_us,
            "sd_us": sd_us,
            "bootstrap_95_ci_us": ci_us,
        })

    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "stages": STAGES,
        "summary": summary,
        "interpretation": (
            "Stage-decomposed latency of the reactive Packet-In path (real "
            "OpenFlow Packet-In -> NO_RULE -> DAIM Core decision -> "
            "confirmed installed OVS rule), 30 randomised-order repetitions "
            "per adapter mode. Extends the prior functional-only Packet-In "
            "acceptance test (STAGE_PACKETIN_BRIDGE_REPORT.md) with a real "
            "latency distribution, addressing the construct- and "
            "internal-validity threats named in the manuscript for this "
            "specific experiment."
        ),
    }
    (OUT / "packetin_latency_breakdown_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(summary, OUT / "packetin_latency_breakdown.png")
    print(OUT / "packetin_latency_breakdown_statistics.json")
    print(OUT / "packetin_latency_breakdown.png")


if __name__ == "__main__":
    main()
