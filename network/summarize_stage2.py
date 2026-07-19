#!/usr/bin/env python3
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = ROOT / "results/network/stage2_raw.csv"
summary = ROOT / "results/network/stage2_summary.csv"
rows = list(csv.DictReader(raw.open()))

def percentile(values, q):
    values = sorted(values)
    if len(values) == 1: return values[0]
    rank = (len(values) - 1) * q
    lo, hi = int(rank), min(len(values) - 1, int(rank) + 1)
    return values[lo] + (values[hi] - values[lo]) * (rank - lo)

out = []
for size in sorted({int(r["network_size"]) for r in rows}):
    group = [r for r in rows if int(r["network_size"]) == size]
    means = [float(r["install_mean_us"]) for r in group]
    sums = [float(r["install_sum_us"]) for r in group]
    out.append({
        "evidence_level": "measured_emulation",
        "network_size": size,
        "n": len(group),
        "ping_success_count": sum(int(r["ping_success"]) for r in group),
        "install_mean_us_mean": statistics.fmean(means),
        "install_mean_us_p50": percentile(means, .50),
        "install_mean_us_p95": percentile(means, .95),
        "install_mean_us_p99": percentile(means, .99),
        "install_sum_us_mean": statistics.fmean(sums),
        "python_max_rss_kib_max": max(int(r["python_max_rss_kib"]) for r in group),
        "python_cpu_s_max": max(float(r["python_user_cpu_s"]) + float(r["python_system_cpu_s"]) for r in group),
    })
with summary.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(out[0])); writer.writeheader(); writer.writerows(out)
print(json.dumps({"evidence_level":"measured_emulation", "summary":str(summary), "rows":len(out)}, indent=2))

