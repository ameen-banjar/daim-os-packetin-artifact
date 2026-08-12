#!/usr/bin/env python3
"""Analyse the matched reactive Packet-In benchmark.

All modes start at Os-Ken Packet-In handler entry and finish when the installed
rule is observable through the same OVS dump-flows probe. The DAIM modes retain
their internal C/ctypes decomposition; the DAIM-free Os-Ken baseline exposes
its Python parse, state-update, decision, and native Flow-Mod stages.
"""
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
MODES = ["process_per_rule", "persistent", "reactive_osken"]
LABELS = {
    "process_per_rule": "DAIM: process/rule",
    "persistent": "DAIM: persistent",
    "reactive_osken": "Os-Ken reactive",
}
STAGES = ["controller", "interop", "decision", "table_write", "install_call", "packetout", "confirm"]
STAGE_LABELS = {
    "controller": "Controller dispatch / parse",
    "interop": "ctypes boundary",
    "decision": "Learning decision / state",
    "table_write": "DAIM table write",
    "install_call": "Flow installation call",
    "packetout": "PacketOut send",
    "confirm": "Common OVS rule-observation probe",
}
COLORS = {stage: "#333333" for stage in STAGES}


def integer(row, key):
    value = row.get(key)
    return None if value in (None, "") else int(value)


def stage_deltas_us(row):
    mode = row["mode"]
    if mode == "reactive_osken":
        start = integer(row, "t_dispatch_enter_ns")
        parsed = integer(row, "t_parse_done_ns")
        state_done = integer(row, "t_state_update_done_ns")
        decision_done = integer(row, "t_decision_done_ns")
        install_done = integer(row, "t_flowmod_sent_ns")
        packetout_done = integer(row, "t_packetout_sent_ns")
        confirmed = integer(row, "t_confirmed_ns")
        values = {
            "controller": parsed - start,
            "interop": 0,
            "decision": decision_done - parsed,
            "table_write": 0,
            "install_call": install_done - decision_done,
            "packetout": packetout_done - install_done,
            "confirm": confirmed - packetout_done if confirmed is not None else None,
            "total": confirmed - start if confirmed is not None else None,
        }
    else:
        dispatch = integer(row, "t_dispatch_enter_ns")
        pre_ctypes = integer(row, "t_pre_ctypes_ns")
        c_entry = integer(row, "c_entry_ns")
        decision_done = integer(row, "c_decision_done_ns")
        table_done = integer(row, "c_table_write_done_ns")
        install_done = integer(row, "c_install_done_ns")
        c_exit = integer(row, "c_exit_ns")
        post_ctypes = integer(row, "t_post_ctypes_ns")
        packetout_done = integer(row, "t_packetout_sent_ns")
        confirmed = integer(row, "t_confirmed_ns")
        values = {
            "controller": pre_ctypes - dispatch,
            "interop": (c_entry - pre_ctypes) + (post_ctypes - c_exit),
            "decision": decision_done - c_entry,
            "table_write": table_done - decision_done,
            "install_call": install_done - table_done,
            "packetout": packetout_done - post_ctypes,
            "confirm": confirmed - packetout_done if confirmed is not None else None,
            "total": confirmed - dispatch if confirmed is not None else None,
        }
    return {key: (value / 1000.0 if value is not None else None) for key, value in values.items()}


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def descriptive(values, rng):
    data = np.asarray(values, dtype=float)
    return {
        "n": int(len(data)),
        "mean_us": float(np.mean(data)),
        "sd_us": float(np.std(data, ddof=1)) if len(data) > 1 else 0.0,
        "median_us": float(np.median(data)),
        "p95_us": float(np.percentile(data, 95)),
        "p99_us": float(np.percentile(data, 99)),
        "max_us": float(np.max(data)),
        "bootstrap_mean_95_ci_us": bootstrap_ci(data, rng),
    }


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def draw_chart(summary, path):
    width, height = 1900, 1560
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font, label_font, axis_font, note_font = font(46, True), font(36), font(32), font(31)
    left, top, right, bottom = 390, 125, 1810, 485
    draw.text((left, 30), "Matched reactive Packet-In latency", fill="#111111", font=title_font)
    draw.text((25, 82), "A. Total latency distribution", fill="#111111", font=label_font)
    draw.line((left, top, left, bottom), fill="#222222", width=3)
    draw.line((left, bottom, right, bottom), fill="#222222", width=3)
    max_total = max(item["total"]["max_us"] for item in summary) * 1.04

    def x_of(value):
        return left + (value / max_total) * (right - left)

    bar_h = 30
    for idx, item in enumerate(summary):
        y0 = top + 62 + idx * 102
        total = item["total"]
        draw.text((30, y0 - 16), LABELS[item["mode"]], fill="#111111", font=label_font)
        draw.line((x_of(total["median_us"]), y0, x_of(total["p99_us"]), y0), fill="#C8D3E0", width=12)
        draw.ellipse((x_of(total["median_us"])-9, y0-9, x_of(total["median_us"])+9, y0+9), fill="#0072B2")
        xp95 = x_of(total["p95_us"])
        draw.rectangle((xp95-9, y0-9, xp95+9, y0+9), outline="#E69F00", fill="white", width=4)
        xp99 = x_of(total["p99_us"])
        draw.polygon([(xp99,y0-11),(xp99-11,y0+9),(xp99+11,y0+9)], outline="#7A5195", fill="white")
        tail = f"median {total['median_us']/1000:.3f}  |  p95 {total['p95_us']/1000:.3f}  |  p99 {total['p99_us']/1000:.3f} ms"
        draw.text((left, y0 + 24), tail, fill="#333333", font=note_font)

    tick_step = max_total / 6
    for idx in range(7):
        value = idx * tick_step
        x = x_of(value)
        draw.line((x, top, x, bottom), fill="#E5E5E5", width=1)
        draw.text((x - 30, bottom + 12), f"{value/1000:.1f}", fill="#222222", font=axis_font)
    draw.text((left + 540, bottom + 55), "Latency (ms)", fill="#222222", font=label_font)
    key_y = 548
    draw.ellipse((40, key_y, 62, key_y + 22), fill="#0072B2"); draw.text((74, key_y - 6), "median", fill="#111111", font=note_font)
    draw.rectangle((250, key_y, 272, key_y + 22), outline="#E69F00", fill="white", width=5); draw.text((284, key_y - 6), "p95", fill="#111111", font=note_font)
    draw.polygon([(440,key_y-2),(428,key_y+22),(452,key_y+22)], outline="#7A5195", fill="white"); draw.text((466, key_y - 6), "p99", fill="#111111", font=note_font)

    mode_colors = ["#0072B2", "#D55E00", "#009E73"]
    offsets = [-28, 0, 28]

    def marker(x, y, mi):
        color = mode_colors[mi]
        if mi == 0: draw.ellipse((x-10,y-10,x+10,y+10), fill=color)
        elif mi == 1: draw.rectangle((x-10,y-10,x+10,y+10), outline=color, width=5, fill="white")
        else: draw.polygon([(x,y-12),(x-12,y+10),(x+12,y+10)], outline=color, fill="white")

    def stage_panel(title, stages, unit, divisor, ptop, pbottom):
        draw.text((25, ptop-60), title, fill="#111111", font=label_font)
        plot_right = 1540
        max_value = max(item["stage_mean_us"][s]/divisor for s in stages for item in summary) * 1.18 or 1
        def px(value): return left + (value/max_value)*(plot_right-left)
        for ti in range(6):
            value = max_value*ti/5
            x = px(value)
            draw.line((x,ptop-10,x,pbottom), fill="#E1E7EF", width=1)
            draw.text((x-20,pbottom+6),f"{value:.2f}" if max_value<10 else f"{value:.0f}",fill="#333333",font=note_font)
        row_h=(pbottom-ptop)/len(stages)
        for si, stage in enumerate(stages):
            y=ptop+(si+0.5)*row_h
            draw.text((25,y-14),STAGE_LABELS[stage],fill="#222222",font=note_font)
            for mi,item in enumerate(summary):
                value=item["stage_mean_us"][stage]/divisor
                yy=y+offsets[mi]
                x=px(value)
                marker(x,yy,mi)
                draw.text((x+16,yy-14),f"{value:.3f}" if value<1 else f"{value:.2f}",fill=mode_colors[mi],font=font(27, True))
        draw.text((left+450,pbottom+42),f"Mean stage latency ({unit}, linear scale)",fill="#222222",font=label_font)

    stage_panel("B. Internal processing stages", ["controller","interop","decision","table_write","packetout"], "µs", 1.0, 650, 1010)
    stage_panel("C. Southbound and switch-observation stages", ["install_call","confirm"], "ms", 1000.0, 1160, 1335)

    ly = 1500
    marker(70,ly,0); draw.text((98,ly-16),"DAIM process/rule",fill="#111111",font=note_font)
    marker(560,ly,1); draw.text((588,ly-16),"DAIM persistent",fill="#111111",font=note_font)
    marker(1040,ly,2); draw.text((1068,ly-16),"Os-Ken reactive",fill="#111111",font=note_font)
    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)
    summary = []
    for mode in MODES:
        rows = [row for row in raw if row["mode"] == mode]
        deltas = [stage_deltas_us(row) for row in rows]
        stage_stats = {}
        for stage in STAGES:
            values = [item[stage] for item in deltas if item[stage] is not None]
            stage_stats[stage] = descriptive(values, rng) if values else None
        totals = [item["total"] for item in deltas if item["total"] is not None]
        summary.append({
            "mode": mode,
            "n": len(rows),
            "confirmed_n": len(totals),
            "ping_success_n": sum(int(row["ping_success"]) for row in rows),
            "priming_ok_n": sum(int(row["priming_ok"]) for row in rows),
            "installed_n": sum(row.get("installed") in ("True", "1", "true") for row in rows),
            "stage_statistics": stage_stats,
            "stage_mean_us": {stage: stage_stats[stage]["mean_us"] if stage_stats[stage] else 0.0 for stage in STAGES},
            "total": descriptive(totals, rng),
        })

    by_mode = {item["mode"]: item for item in summary}
    comparison = {
        "persistent_vs_reactive_osken_mean_ratio": by_mode["persistent"]["total"]["mean_us"] / by_mode["reactive_osken"]["total"]["mean_us"],
        "persistent_vs_reactive_osken_median_ratio": by_mode["persistent"]["total"]["median_us"] / by_mode["reactive_osken"]["total"]["median_us"],
        "process_vs_reactive_osken_mean_ratio": by_mode["process_per_rule"]["total"]["mean_us"] / by_mode["reactive_osken"]["total"]["mean_us"],
    }
    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "common_completion_semantics": "Packet-In handler entry to rule observable by ovs-ofctl dump-flows",
        "summary": summary,
        "comparison": comparison,
        "interpretation": (
            "Randomised matched L2-learning comparison: both DAIM modes and the "
            "DAIM-free Os-Ken controller process the same first Packet-In for a "
            "known destination, install the same priority/match/action rule, and "
            "end at the same switch-side rule-observation boundary."
        ),
    }
    stats_path = OUT / "packetin_latency_breakdown_statistics.json"
    figure_path = OUT / "packetin_latency_breakdown.png"
    stats_path.write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(summary, figure_path)
    print(stats_path)
    print(figure_path)


if __name__ == "__main__":
    main()
