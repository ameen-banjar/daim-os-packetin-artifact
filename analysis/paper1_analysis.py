#!/usr/bin/env python3
"""Reproduce Paper 1 summary statistics and figures from measured raw data."""

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/stage2_baseline_raw.csv"
OUT = ROOT / "results/paper1"
SEED = 20260718
BOOTSTRAPS = 20000


def bootstrap_ci(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(BOOTSTRAPS, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def effect_size(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    pooled = np.sqrt(
        ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
        / (len(a) + len(b) - 2)
    )
    return float((a.mean() - b.mean()) / pooled)


def draw_chart(rows, path):
    width, height = 1500, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=20)
    left, top, right, bottom = 130, 80, 1420, 760
    draw.line((left, top, left, bottom), fill="#222222", width=3)
    draw.line((left, bottom, right, bottom), fill="#222222", width=3)
    ymax = 18.0
    for tick in range(0, 19, 3):
        y = bottom - (tick / ymax) * (bottom - top)
        draw.line((left - 8, y, right, y), fill="#dddddd", width=1)
        draw.text((45, y - 12), str(tick), fill="#222222", font=small)
    sizes = sorted({r["network_size"] for r in rows})
    modes = ["daim_adapter", "direct_ovs"]
    colors = {"daim_adapter": "#2457A6", "direct_ovs": "#C45A24"}
    labels = {"daim_adapter": "DAIM adapter", "direct_ovs": "Direct ovs-ofctl"}
    offsets = {"daim_adapter": -6, "direct_ovs": 6}

    def y_of(value):
        return bottom - (value / ymax) * (bottom - top)

    for mode in modes:
        points = []
        for idx, size in enumerate(sizes):
            row = next(r for r in rows if r["network_size"] == size and r["mode"] == mode)
            x = left + idx * (right - left) / (len(sizes) - 1) + offsets[mode]
            y = y_of(row["mean_ms"])
            points.append((x, y))
            lo, hi = row["bootstrap_95_ci_ms"]
            y_lo, y_hi = y_of(lo), y_of(hi)
            draw.line((x, y_lo, x, y_hi), fill=colors[mode], width=2)
            draw.line((x - 7, y_lo, x + 7, y_lo), fill=colors[mode], width=2)
            draw.line((x - 7, y_hi, x + 7, y_hi), fill=colors[mode], width=2)
        draw.line(points, fill=colors[mode], width=6)
        for x, y in points:
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=colors[mode])
    for idx, size in enumerate(sizes):
        x = left + idx * (right - left) / (len(sizes) - 1)
        draw.text((x - 18, bottom + 18), str(size), fill="#222222", font=font)
    draw.text((530, 815), "Number of OVS switches", fill="#222222", font=font)
    draw.text((20, 20), "Mean per-switch rule installation time (ms), whiskers = bootstrap 95% CI", fill="#222222", font=font)
    draw.rectangle((1000, 95, 1030, 125), fill=colors["daim_adapter"])
    draw.text((1045, 95), labels["daim_adapter"], fill="#222222", font=small)
    draw.rectangle((1000, 140, 1030, 170), fill=colors["direct_ovs"])
    draw.text((1045, 140), labels["direct_ovs"], fill="#222222", font=small)
    image.save(path)


def box(draw, xy, text, font, fill="#EFF3F9", outline="#2457A6", text_color="#1F2933"):
    x0, y0, x1, y1 = xy
    draw.rectangle(xy, fill=fill, outline=outline, width=3)
    lines = text.split("\n")
    line_h = font.size + 6
    total_h = line_h * len(lines)
    ty = y0 + ((y1 - y0) - total_h) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x0 + ((x1 - x0) - tw) / 2, ty), line, fill=text_color, font=font)
        ty += line_h


def h_arrow(draw, x0, x1, y, label, font, color="#333333", dashed=False, label_dy=-26):
    if dashed:
        step = 14
        xx = x0
        while xx < x1 - step:
            draw.line((xx, y, xx + step * 0.6, y), fill=color, width=2)
            xx += step
    else:
        draw.line((x0, y, x1, y), fill=color, width=3)
    direction = 1 if x1 >= x0 else -1
    ax = x1
    draw.polygon(
        [(ax, y), (ax - 14 * direction, y - 7), (ax - 14 * direction, y + 7)], fill=color
    )
    if label:
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((min(x0, x1) + abs(x1 - x0) / 2 - tw / 2, y + label_dy), label, fill=color, font=font)


def v_arrow(draw, x, y0, y1, label, font, color="#333333", label_dx=10):
    draw.line((x, y0, x, y1), fill=color, width=3)
    direction = 1 if y1 >= y0 else -1
    ay = y1
    draw.polygon(
        [(x, ay), (x - 7, ay - 14 * direction), (x + 7, ay - 14 * direction)], fill=color
    )
    if label:
        draw.text((x + label_dx, min(y0, y1) + abs(y1 - y0) / 2 - 10), label, fill=color, font=font)


def draw_architecture(path):
    width, height = 1700, 1010
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=26)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=17)

    draw.text((20, 20), "DAIM-OS table-and-signal control path: component architecture", fill="#111111", font=title_font)

    host = (60, 150, 300, 230)
    switch = (420, 150, 720, 230)
    controller = (840, 150, 1180, 230)
    bridge = (840, 380, 1180, 460)
    core = (840, 590, 1180, 690)
    app = (560, 800, 900, 890)
    adapter = (1040, 800, 1380, 890)

    box(draw, host, "Mininet host (h1)", font)
    box(draw, switch, "Open vSwitch bridge\n(OpenFlow 1.3)", font)
    box(draw, controller, "Os-Ken controller\n(daim_bridge_controller.py)", font)
    box(draw, bridge, "ctypes bridge\n(daim_core_bridge.py)", font)
    box(draw, core, "libdaim_core.so\nDAIM Core: tables + NO_RULE signal", font, fill="#FDF3E7", outline="#C45A24")
    box(draw, app, "Learning application\n(daim_learning_app.c)\nwrites PACKET_FORWARDING_TABLE", small, fill="#FDF3E7", outline="#C45A24")
    box(draw, adapter, "OVS adapter\n(posix_spawnp -> ovs-ofctl)", font, fill="#FDF3E7", outline="#C45A24")

    h_arrow(draw, host[2], switch[0], 178, "traffic", small, label_dy=-26)

    # switch <-> controller: routed above/below the boxes so labels never
    # cross box borders or text.
    sx, cx = 650, 900
    draw.line((sx, switch[1], sx, 100), fill="#333333", width=3)
    draw.line((sx, 100, cx, 100), fill="#333333", width=3)
    v_arrow(draw, cx, 100, controller[1], "", small)
    draw.text((sx + 30, 78), "Packet-In (table-miss)", fill="#333333", font=small)

    draw.line((cx, controller[3], cx, 275), fill="#666666", width=2)
    draw.line((cx, 275, sx, 275), fill="#666666", width=2)
    v_arrow(draw, sx, 275, switch[3], "", small, color="#666666")
    draw.text((sx + 30, 282), "PacketOut (buffered packet)", fill="#666666", font=small)

    v_arrow(draw, 1010, controller[3], bridge[1], "packet_in(bridge, in_port,\nmac_src, mac_dst)", small)
    v_arrow(draw, 1010, bridge[3], core[1], "daim_core_emit(NO_RULE, info)", small)

    # core -> app: right-angle connector down and left, single label
    core_app_y = 745
    draw.line((core[0] + 60, core[3], core[0] + 60, core_app_y), fill="#333333", width=3)
    draw.line((core[0] + 60, core_app_y, app[0] + 170, core_app_y), fill="#333333", width=3)
    v_arrow(draw, app[0] + 170, core_app_y, app[1], "invoke registered NO_RULE handler", small, label_dx=14)

    # app -> adapter
    h_arrow(draw, app[2], adapter[0], 845, "flow_add(bridge, match+action)\nif destination known", small, label_dy=-40)

    # adapter -> switch (installs rule): long return arrow up the right side,
    # then left along a lane above the title-adjacent margin and down into
    # the switch box at a point clear of the Packet-In/PacketOut stubs.
    x_return = 1600
    sw_target = 500
    draw.line((adapter[2], 845, x_return, 845), fill="#2457A6", width=3)
    draw.line((x_return, 845, x_return, 65), fill="#2457A6", width=3)
    draw.line((x_return, 65, sw_target, 65), fill="#2457A6", width=3)
    v_arrow(draw, sw_target, 65, switch[1], "", small, color="#2457A6")
    draw.text((1360, 480), "ovs-ofctl\nadd-flow\n(installs\nrule)", fill="#2457A6", font=small)

    draw.text((20, 950), "Grey = controller-owned wire path. Orange boxes = DAIM Core/application/adapter (this paper's implemented subset). The table-write step is shown in Figure 2.", fill="#555555", font=small)
    image.save(path)


def draw_sequence(path):
    width, height = 1700, 1150
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=26)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=16)

    draw.text((20, 20), "Packet-In -> NO_RULE -> installed OVS rule: message sequence", fill="#111111", font=title_font)

    actors = [
        ("Host", 90),
        ("OVS switch", 330),
        ("Os-Ken\ncontroller", 570),
        ("ctypes bridge", 830),
        ("DAIM Core\n(libdaim_core.so)", 1110),
        ("Learning\napplication", 1370),
        ("OVS adapter", 1590),
    ]
    top_y = 70
    bottom_y = 1080
    for name, x in actors:
        box(draw, (x - 90, top_y, x + 90, top_y + 70), name, font)
        draw.line((x, top_y + 70, x, bottom_y), fill="#BBBBBB", width=2)

    xs = {name: x for name, x in actors}
    steps = [
        ("Host", "OVS switch", "ICMP/ARP packet", False),
        ("OVS switch", "Os-Ken\ncontroller", "Packet-In (no matching flow)", False),
        ("Os-Ken\ncontroller", "ctypes bridge", "packet_in(bridge, in_port, mac_src, mac_dst)", False),
        ("ctypes bridge", "DAIM Core\n(libdaim_core.so)", "daim_core_emit(NO_RULE, info)", False),
        ("DAIM Core\n(libdaim_core.so)", "Learning\napplication", "invoke registered NO_RULE handler", False),
        ("Learning\napplication", "DAIM Core\n(libdaim_core.so)", "daim_table_write(FORWARDING_TABLE, ADD)", True),
        ("Learning\napplication", "OVS adapter", "flow_add(bridge, match+action) [if destination known]", False),
        ("OVS adapter", "OVS switch", "ovs-ofctl add-flow (installs rule)", False),
        ("Os-Ken\ncontroller", "OVS switch", "PacketOut (buffered packet)", True),
    ]
    y = 190
    step_h = 100
    for src, dst, label, dashed in steps:
        x0, x1 = xs[src], xs[dst]
        h_arrow(draw, x0, x1, y, label, small, color="#2457A6" if not dashed else "#888888", dashed=dashed, label_dy=-20)
        y += step_h

    draw.text((20, 1100), "Dashed arrows = messages already possible without DAIM (return path / persistence).", fill="#555555", font=small)
    image.save(path)


def draw_topology(path):
    width, height = 1700, 1020
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=24)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=17)
    tiny = ImageFont.load_default(size=15)

    # Panel A: two-switch Packet-In experiment topology (Section 5.3)
    draw.text((40, 30), "(a) Packet-In experiment topology (Section 5.3)", fill="#111111", font=title_font)
    ax_y = 170
    a_boxes = [
        ("h1", 60, "#EFF3F9", "#2457A6"),
        ("s1\n(OVS)", 280, "#FDF3E7", "#C45A24"),
        ("s2\n(OVS)", 560, "#FDF3E7", "#C45A24"),
        ("h2", 780, "#EFF3F9", "#2457A6"),
    ]
    prev = None
    for label, x, fill, outline in a_boxes:
        bx = (x, ax_y - 45, x + 140, ax_y + 45)
        box(draw, bx, label, font, fill=fill, outline=outline)
        if prev is not None:
            h_arrow(draw, prev, bx[0], ax_y, "", small)
            draw.line((prev, ax_y, bx[0], ax_y), fill="#333333", width=3)
        prev = bx[2]
    draw.text((40, 260), "One host per end switch; Os-Ken bridge controller\nattached out-of-band to both switches.", fill="#555555", font=tiny)

    # Panel B: linear N-switch adapter-overhead microbenchmark (Section 5.4)
    by0 = 610
    draw.text((40, 420), "(b) Adapter-overhead microbenchmark topology (Section 5.4),\nN = 8, 16, 32, or 64", fill="#111111", font=title_font)
    xs = [60, 260, 460, 900, 1100, 1300]
    labels = ["s1", "s2", "s3", "...", "s(N-1)", "sN"]
    centers = []
    for lab, x in zip(labels, xs):
        if lab == "...":
            draw.text((x, by0 - 12), "...", fill="#555555", font=title_font)
            centers.append(x + 15)
            continue
        bx = (x, by0 - 35, x + 120, by0 + 35)
        fill, outline = ("#FDF3E7", "#C45A24")
        box(draw, bx, lab, small, fill=fill, outline=outline)
        centers.append((bx[0] + bx[2]) / 2)
        hbx = (x + 10, by0 + 90, x + 110, by0 + 150)
        box(draw, hbx, "h", tiny, fill="#EFF3F9", outline="#2457A6")
        v_arrow(draw, (hbx[0] + hbx[2]) / 2, hbx[1], bx[3], "", tiny)
    for i in range(len(centers) - 1):
        if labels[i] == "..." or labels[i + 1] == "...":
            x0 = centers[i] + (25 if labels[i] != "..." else 0)
            x1 = centers[i + 1] - (25 if labels[i + 1] != "..." else 0)
        else:
            x0, x1 = centers[i] + 60, centers[i + 1] - 60
        draw.line((x0, by0, x1, by0), fill="#333333", width=3)
    draw.text((40, 820), "One host per switch; each switch receives one priority=100,ip,actions=normal rule.\nEvery topology rebuilt and cleaned before each of the 5 repetitions per (mode, N).", fill="#555555", font=tiny)

    # Testbed info box
    info_box = (40, 900, 1660, 1000)
    draw.rectangle(info_box, fill="#F4F6F9", outline="#888888", width=2)
    draw.text((60, 918), "Testbed: Ubuntu 24.04 LTS ARM64, Lima/QEMU VM (4 vCPU, 6 GiB RAM)  ·  Open vSwitch 3.3.4  ·  Mininet 2.3.0  ·  OpenFlow 1.3  ·  Os-Ken 2.6.0", fill="#222222", font=small)
    draw.text((60, 948), "Core/adapter conformance tests were additionally run on macOS ARM64, Apple Clang 21.0.0 (Section 5.1).", fill="#555555", font=tiny)

    image.save(path)


def draw_comparison(path):
    width, height = 1700, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=24)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=16)

    draw.text((20, 20), "DAIM literature (2013-2018) versus this paper's executable artifact (2026)", fill="#111111", font=title_font)

    left = (60, 100, 760, 650)
    right = (1040, 100, 1640, 650)
    draw.rectangle(left, fill="#F4F6F9", outline="#666666", width=3)
    draw.rectangle(right, fill="#FDF3E7", outline="#C45A24", width=3)
    draw.text((left[0] + 24, left[1] + 20), "DAIM literature, 2013-2018 [1-3, 17, 18, 31, 32]", fill="#222222", font=font)
    draw.text((right[0] + 24, right[1] + 20), "This paper, 2026", fill="#222222", font=font)

    left_items = [
        "Switch-local agents and active-information",
        "concept (reactive interpreter, 2013)",
        "",
        "Architecture, tables/signals concept, and",
        "risk scenarios described in prose (2014)",
        "",
        "OMNeT++/Mininet simulation and staged",
        "implementation studies (2014-2015)",
        "",
        "Distributed controller prototype with",
        "Cbench throughput/latency (2018)",
        "",
        "DAIM-OS specification consolidated:",
        "tables, signals, APIs (2016 dissertation)",
    ]
    right_items = [
        "Mutex-protected C core: 5 writable tables,",
        "generation tracking, sanitizer-clean",
        "",
        "Real OpenFlow 1.3 Packet-In -> NO_RULE",
        "-> DAIM table -> installed OVS rule",
        "",
        "Os-Ken + ctypes bridge; Python holds no",
        "learning state, only the wire session",
        "",
        "Matched 40-run adapter-overhead",
        "microbenchmark with bootstrap CIs",
        "",
        "Versioned artifact: raw data, checksums,",
        "failure record, analysis script",
    ]
    ty = left[1] + 70
    for line in left_items:
        draw.text((left[0] + 24, ty), line, fill="#333333", font=small)
        ty += 34
    ty = right[1] + 70
    for line in right_items:
        draw.text((right[0] + 24, ty), line, fill="#333333", font=small)
        ty += 34

    h_arrow(draw, left[2] + 15, right[0] - 15, 300, "", small)
    draw.text((left[2] + 25, 330), "same table/signal\nabstractions; new\nexecutable artifact\nand evidence", fill="#2457A6", font=small)

    draw.text((20, 700), "No historical DAIM performance number is reused in this paper; the right column lists what is newly measured here (Section 2.3).", fill="#555555", font=small)
    image.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with RAW.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rng = np.random.default_rng(SEED)
    summary = []
    comparisons = []
    for size in (8, 16, 32, 64):
        by_mode = {}
        for mode in ("daim_adapter", "direct_ovs"):
            values = [
                float(row["install_mean_us"]) / 1000.0
                for row in raw
                if int(row["network_size"]) == size and row["mode"] == mode
            ]
            by_mode[mode] = values
            summary.append(
                {
                    "network_size": size,
                    "mode": mode,
                    "n": len(values),
                    "mean_ms": float(np.mean(values)),
                    "sd_ms": float(np.std(values, ddof=1)),
                    "median_ms": float(np.median(values)),
                    "bootstrap_95_ci_ms": bootstrap_ci(values, rng),
                    "connectivity_passes": sum(
                        int(row["ping_success"])
                        for row in raw
                        if int(row["network_size"]) == size and row["mode"] == mode
                    ),
                }
            )
        a, b = by_mode["daim_adapter"], by_mode["direct_ovs"]
        comparisons.append(
            {
                "network_size": size,
                "mean_difference_ms": float(np.mean(a) - np.mean(b)),
                "mean_ratio": float(np.mean(a) / np.mean(b)),
                "cohens_d": effect_size(a, b),
            }
        )
    result = {
        "evidence_level": "measured_emulation",
        "source": str(RAW.relative_to(ROOT)),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "summary": summary,
        "comparisons": comparisons,
        "interpretation": (
            "This benchmark measures process-mediated rule installation in the "
            "recorded harness; it is not controller throughput or end-to-end "
            "new-flow latency."
        ),
    }
    (OUT / "paper1_statistics.json").write_text(json.dumps(result, indent=2) + "\n")
    draw_chart(summary, OUT / "paper1_installation_time.png")
    draw_architecture(OUT / "paper1_architecture.png")
    draw_sequence(OUT / "paper1_sequence.png")
    draw_topology(OUT / "paper1_topology.png")
    draw_comparison(OUT / "paper1_comparison.png")
    print(OUT / "paper1_statistics.json")
    print(OUT / "paper1_installation_time.png")
    print(OUT / "paper1_architecture.png")
    print(OUT / "paper1_sequence.png")
    print(OUT / "paper1_topology.png")
    print(OUT / "paper1_comparison.png")


if __name__ == "__main__":
    main()
