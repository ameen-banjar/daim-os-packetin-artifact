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

def styled_segment(draw, a, b, style="solid", width=4, color="#111111"):
    x0,y0=a; x1,y1=b
    length=max(1.0,((x1-x0)**2+(y1-y0)**2)**0.5)
    pattern=[length] if style=="solid" else [24,12]
    pos=0.0; pi=0; on=True
    while pos<length:
        end=min(length,pos+pattern[pi%len(pattern)])
        if on:
            draw.line((x0+(x1-x0)*pos/length,y0+(y1-y0)*pos/length,x0+(x1-x0)*end/length,y0+(y1-y0)*end/length),fill=color,width=width)
        pos=end; pi+=1; on=not on


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
    font = ImageFont.load_default(size=36)
    small = ImageFont.load_default(size=38)
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
    colors = {"daim_adapter": "#0072B2", "direct_ovs": "#D55E00"}
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
        for a, b in zip(points, points[1:]):
            styled_segment(draw, a, b, "solid" if mode == "daim_adapter" else "dashed", 5 if mode == "daim_adapter" else 3, colors[mode])
        for x, y in points:
            if mode == "daim_adapter":
                draw.ellipse((x-9,y-9,x+9,y+9),fill=colors[mode])
            else:
                draw.rectangle((x-9,y-9,x+9,y+9),outline=colors[mode],width=4,fill="white")
    for idx, size in enumerate(sizes):
        x = left + idx * (right - left) / (len(sizes) - 1)
        draw.text((x - 18, bottom + 18), str(size), fill="#222222", font=font)
    draw.text((530, 815), "Number of OVS switches", fill="#222222", font=font)
    draw.text((20, 20), "Mean per-switch rule installation time (ms), whiskers = bootstrap 95% CI", fill="#222222", font=font)
    draw.ellipse((206, 121, 224, 139), fill=colors["daim_adapter"])
    styled_segment(draw, (190,130), (238,130), "solid", 4, colors["daim_adapter"])
    draw.text((245, 115), labels["daim_adapter"], fill="#222222", font=small)
    draw.rectangle((206, 166, 224, 184), outline=colors["direct_ovs"], width=3, fill="white")
    styled_segment(draw, (190,175), (238,175), "dashed", 3, colors["direct_ovs"])
    draw.text((245, 160), labels["direct_ovs"], fill="#222222", font=small)
    image.save(path)


def dashed_rectangle(draw, xy, outline, width=3, dash=14, gap=8, dotted=False):
    x0, y0, x1, y1 = xy
    if dotted:
        dash, gap = width + 1, 10
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for (ex0, ey0), (ex1, ey1) in edges:
        length = ((ex1 - ex0) ** 2 + (ey1 - ey0) ** 2) ** 0.5
        if length == 0:
            continue
        ux, uy = (ex1 - ex0) / length, (ey1 - ey0) / length
        pos = 0.0
        draw_on = True
        while pos < length:
            step = dash if draw_on else gap
            end = min(length, pos + step)
            if draw_on:
                draw.line((ex0 + ux * pos, ey0 + uy * pos, ex0 + ux * end, ey0 + uy * end), fill=outline, width=width)
            pos = end
            draw_on = not draw_on


def box(draw, xy, text, font, fill="#F1F1F1", outline="#333333", text_color="#1F2933", border="solid", tag=None, tag_font=None, tag_color=None):
    x0, y0, x1, y1 = xy
    draw.rectangle(xy, fill=fill)
    if border == "solid":
        draw.rectangle(xy, outline=outline, width=3)
    elif border == "dashed":
        dashed_rectangle(draw, xy, outline, width=3, dash=16, gap=10)
    elif border == "dotted":
        dashed_rectangle(draw, xy, outline, width=4, dotted=True)
    lines = text.split("\n") if text else []
    line_h = font.size + 6
    tag_h = (tag_font.size + 6) if tag else 0
    total_h = line_h * len(lines) + tag_h
    ty = y0 + ((y1 - y0) - total_h) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x0 + ((x1 - x0) - tw) / 2, ty), line, fill=text_color, font=font)
        ty += line_h
    if tag:
        bbox = draw.textbbox((0, 0), tag, font=tag_font)
        tw = bbox[2] - bbox[0]
        draw.text((x0 + ((x1 - x0) - tw) / 2, ty + 4), tag, fill=tag_color or outline, font=tag_font)


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
        tx = min(x0, x1) + abs(x1 - x0) / 2 - tw / 2
        ty = y + label_dy
        draw.rectangle((tx - 8, ty - 3, tx + tw + 8, ty + font.size + 4), fill="white")
        draw.text((tx, ty), label, fill=color, font=font)


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
    width, height = 1800, 1150
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=42)
    font = ImageFont.load_default(size=30)
    small = ImageFont.load_default(size=32)

    draw.text((20, 20), "DAIM-OS table-and-signal control path: component architecture", fill="#111111", font=title_font)

    host = (30, 180, 310, 270)
    switch = (400, 180, 790, 270)
    controller = (930, 180, 1270, 270)
    bridge = (930, 400, 1270, 490)
    core = (900, 610, 1300, 720)
    app = (540, 850, 940, 950)
    adapter = (1080, 850, 1560, 950)

    EXT_FILL, EXT_LINE = "#EAF2FB", "#0072B2"
    GLUE_FILL, GLUE_LINE = "#F0EAFB", "#6B4E9E"
    DAIM_FILL, DAIM_LINE = "#FFF0E6", "#D55E00"
    tag_font = ImageFont.load_default(size=24)

    EXT_TAG = "[external dependency]"
    GLUE_TAG = "[glue code, this artifact]"
    DAIM_TAG = "[DAIM-OS concept, impl. here]"

    box(draw, host, "Mininet host (h1)", font, fill=EXT_FILL, outline=EXT_LINE, border="solid",
        tag=EXT_TAG, tag_font=tag_font, tag_color=EXT_LINE)
    box(draw, switch, "OVS switch, OpenFlow 1.3", font, fill=EXT_FILL, outline=EXT_LINE, border="solid",
        tag=EXT_TAG, tag_font=tag_font, tag_color=EXT_LINE)
    box(draw, controller, "Os-Ken controller", font, fill=EXT_FILL, outline=EXT_LINE, border="solid",
        tag=EXT_TAG, tag_font=tag_font, tag_color=EXT_LINE)
    box(draw, bridge, "Python bridge (ctypes)", font, fill=GLUE_FILL, outline=GLUE_LINE, border="dashed",
        tag=GLUE_TAG, tag_font=tag_font, tag_color=GLUE_LINE)
    box(draw, core, "DAIM Core\nTables + NO_RULE", font, fill=DAIM_FILL, outline=DAIM_LINE, border="dotted",
        tag=DAIM_TAG, tag_font=tag_font, tag_color=DAIM_LINE)
    box(draw, app, "DAIM learning application", font, fill=DAIM_FILL, outline=DAIM_LINE, border="dotted",
        tag=DAIM_TAG, tag_font=tag_font, tag_color=DAIM_LINE)
    box(draw, adapter, "OVS adapter (persistent or CLI)", font, fill=DAIM_FILL, outline=DAIM_LINE, border="dotted",
        tag=DAIM_TAG, tag_font=tag_font, tag_color=DAIM_LINE)

    h_arrow(draw, host[2], switch[0], 178, "traffic", small, label_dy=-26)

    # switch <-> controller: routed above/below the boxes so labels never
    # cross box borders or text.
    sx, cx = 660, 1010
    draw.line((sx, switch[1], sx, 115), fill="#333333", width=3)
    draw.line((sx, 115, cx, 115), fill="#333333", width=3)
    v_arrow(draw, cx, 115, controller[1], "", small)
    draw.text((700, 72), "Packet-In (table-miss)", fill="#333333", font=small)

    draw.line((cx, controller[3], cx, 320), fill="#666666", width=2)
    draw.line((cx, 320, sx, 320), fill="#666666", width=2)
    v_arrow(draw, sx, 320, switch[3], "", small, color="#666666")
    draw.text((700, 328), "PacketOut (buffered)", fill="#666666", font=small)

    v_arrow(draw, 1100, controller[3], bridge[1], "Packet-In fields", small, label_dx=18)
    v_arrow(draw, 1100, bridge[3], core[1], "Emit NO_RULE", small, label_dx=18)

    # core -> app: right-angle connector down and left, single label
    core_app_y = 790
    draw.line((core[0] + 70, core[3], core[0] + 70, core_app_y), fill="#333333", width=3)
    draw.line((core[0] + 70, core_app_y, app[0] + 200, core_app_y), fill="#333333", width=3)
    v_arrow(draw, app[0] + 200, core_app_y, app[1], "", small)
    draw.text((app[0] + 215, 795), "Invoke handler", fill="#333333", font=small)

    # app -> adapter
    h_arrow(draw, app[2], adapter[0], 900, "", small)

    # adapter -> switch (installs rule): long return arrow up the right side,
    # then left along a lane above the title-adjacent margin and down into
    # the switch box at a point clear of the Packet-In/PacketOut stubs.
    x_return = 1660
    sw_target = 520
    draw.line((adapter[2], 900, x_return, 900), fill="#111111", width=5)
    draw.line((x_return, 900, x_return, 125), fill="#111111", width=5)
    draw.line((x_return, 125, sw_target, 125), fill="#111111", width=5)
    v_arrow(draw, sw_target, 125, switch[1], "", small, color="#111111")
    draw.text((1420, 520), "Flow-Mod\ninstalls rule", fill="#111111", font=small)

    legend_y = 1005
    row_h = 40
    legend_font = ImageFont.load_default(size=26)

    def legend_swatch_row(x, y, fill, outline, border, text):
        box(draw, (x, y, x + 40, y + 28), "", legend_font, fill=fill, outline=outline, border=border)
        draw.text((x + 52, y + 2), text, fill="#222222", font=legend_font)

    legend_swatch_row(30, legend_y, EXT_FILL, EXT_LINE, "solid", "solid border = external dependency, unmodified")
    legend_swatch_row(950, legend_y, DAIM_FILL, DAIM_LINE, "dotted", "dotted border = DAIM-OS concept, C impl. here")
    legend_swatch_row(30, legend_y + row_h, GLUE_FILL, GLUE_LINE, "dashed", "dashed border = glue code for this artifact")
    draw.text((950, legend_y + row_h + 2), "Border style (not colour alone) marks category", fill="#222222", font=legend_font)
    draw.text((30, legend_y + 2 * row_h), "Heavy black line = Flow-Mod installation", fill="#222222", font=legend_font)
    image.save(path)


def draw_sequence(path):
    width, height = 1700, 1150
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=42)
    font = ImageFont.load_default(size=28)
    small = ImageFont.load_default(size=27)

    draw.text((20, 20), "Packet-In -> NO_RULE -> installed OVS rule: message sequence", fill="#111111", font=title_font)

    actors = [
        ("Host", 120),
        ("OVS switch", 350),
        ("Os-Ken\ncontroller", 590),
        ("ctypes bridge", 830),
        ("DAIM Core\n(libdaim_core.so)", 1080),
        ("Learning\napplication", 1350),
        ("OVS adapter", 1590),
    ]
    top_y = 110
    bottom_y = 1080
    for idx, (name, x) in enumerate(actors):
        implemented = idx >= 4
        box(draw, (x - 100, top_y, x + 100, top_y + 78), name, font,
            fill="#FFF0E6" if implemented else "#EAF2FB",
            outline="#D55E00" if implemented else "#0072B2")
        draw.line((x, top_y + 70, x, bottom_y), fill="#BBBBBB", width=2)

    xs = {name: x for name, x in actors}
    steps = [
        ("Host", "OVS switch", "1  Packet", False),
        ("OVS switch", "Os-Ken\ncontroller", "2  Packet-In", False),
        ("Os-Ken\ncontroller", "ctypes bridge", "3  Bridge callback", False),
        ("ctypes bridge", "DAIM Core\n(libdaim_core.so)", "4  Emit NO_RULE", False),
        ("DAIM Core\n(libdaim_core.so)", "Learning\napplication", "5  Invoke handler", False),
        ("Learning\napplication", "DAIM Core\n(libdaim_core.so)", "6  Write forwarding table", True),
        ("Learning\napplication", "OVS adapter", "7  Install decision", False),
        ("OVS adapter", "OVS switch", "8  Flow-Mod", False),
        ("Os-Ken\ncontroller", "OVS switch", "9  PacketOut", True),
    ]
    y = 230
    step_h = 95
    for src, dst, label, dashed in steps:
        x0, x1 = xs[src], xs[dst]
        h_arrow(draw, x0, x1, y, label, small, color="#111111", dashed=dashed, label_dy=-20)
        y += step_h

    draw.text((20, 1100), "Dashed arrows: return messages already possible without DAIM.", fill="#555555", font=small)
    image.save(path)


def draw_topology(path):
    width, height = 1700, 1020
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=40)
    font = ImageFont.load_default(size=30)
    small = ImageFont.load_default(size=30)
    tiny = ImageFont.load_default(size=27)

    # Panel A: two-switch Packet-In experiment topology (Section 5.3)
    draw.text((40, 30), "(a) Packet-In experiment topology (Section 5.3)", fill="#111111", font=title_font)
    ax_y = 170
    a_boxes = [
        ("h1", 60, "#EAF2FB", "#0072B2"),
        ("s1\n(OVS)", 280, "#FFF0E6", "#D55E00"),
        ("s2\n(OVS)", 560, "#FFF0E6", "#D55E00"),
        ("h2", 780, "#EAF2FB", "#0072B2"),
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
        fill, outline = ("#FFF0E6", "#D55E00")
        box(draw, bx, lab, small, fill=fill, outline=outline)
        centers.append((bx[0] + bx[2]) / 2)
        hbx = (x + 10, by0 + 90, x + 110, by0 + 150)
        box(draw, hbx, "h", tiny, fill="#EAF2FB", outline="#0072B2")
        v_arrow(draw, (hbx[0] + hbx[2]) / 2, hbx[1], bx[3], "", tiny)
    for x0, x1 in [(180,260),(380,460),(580,875),(945,1100),(1220,1300)]:
        draw.line((x0, by0, x1, by0), fill="#333333", width=3)
    draw.text((40, 820), "One host per switch; each switch receives one priority=100,ip,actions=normal rule.\nEvery topology rebuilt and cleaned before each of the 5 repetitions per (mode, N).", fill="#555555", font=tiny)

    # Testbed info box
    info_box = (40, 900, 1660, 1000)
    draw.rectangle(info_box, fill="#F7F9FC", outline="#6B7280", width=2)
    draw.text((60, 912), "Ubuntu 24.04 ARM64 · Lima/QEMU · 4 vCPU · 6 GiB RAM · OVS 3.3.4 · Mininet 2.3.0", fill="#222222", font=small)
    draw.text((60, 952), "OpenFlow 1.3 · Os-Ken 2.6.0. Conformance tests also ran on macOS ARM64 (Section 5.1).", fill="#555555", font=tiny)

    image.save(path)


def draw_comparison(path):
    width, height = 1700, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=40)
    font = ImageFont.load_default(size=32)
    small = ImageFont.load_default(size=30)

    draw.text((20, 20), "DAIM literature (2013-2018) versus this paper's executable artifact (2026)", fill="#111111", font=title_font)

    left = (60, 100, 760, 650)
    right = (1040, 100, 1640, 650)
    draw.rectangle(left, fill="#EAF2FB", outline="#0072B2", width=3)
    draw.rectangle(right, fill="#FFF0E6", outline="#D55E00", width=3)
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
    draw.text((left[2] + 25, 330), "same table/signal\nabstractions; new\nexecutable artifact\nand evidence", fill="#111111", font=small)

    draw.text((20, 700), "No historical DAIM performance result is reused; the right column lists evidence newly produced in this study.", fill="#555555", font=small)
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
