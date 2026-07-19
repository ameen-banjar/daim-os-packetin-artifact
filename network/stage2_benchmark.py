#!/usr/bin/env python3
"""Stage 2 DAIM/OVS scale calibration benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import statistics
import subprocess
import time
from pathlib import Path

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo

ROOT = Path(__file__).resolve().parents[1]
FLOW_CLI = ROOT / "implementation/build/daim_ovs_flow"


class LinearEndpointTopo(Topo):
    def build(self, switches=2):
        nodes = [self.addSwitch(f"s{i}", protocols="OpenFlow13", failMode="secure") for i in range(1, switches + 1)]
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        self.addLink(h1, nodes[0])
        for left, right in zip(nodes, nodes[1:]):
            self.addLink(left, right)
        self.addLink(nodes[-1], h2)


def percentile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    rank = (len(ordered) - 1) * q
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def ovs_rss_kib():
    total = 0
    for pid in subprocess.run(["pgrep", "-x", "ovs-vswitchd"], text=True, capture_output=True).stdout.split():
        try:
            fields = Path(f"/proc/{pid}/status").read_text().splitlines()
            total += int(next(line.split()[1] for line in fields if line.startswith("VmRSS:")))
        except (OSError, StopIteration, ValueError):
            pass
    return total


def available_memory_kib():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    return 0


def command_for(method, bridge, flow):
    if method == "daim_adapter":
        return [str(FLOW_CLI), "add", bridge, flow]
    if method == "direct_ovs_ofctl":
        return ["ovs-ofctl", "-O", "OpenFlow13", "add-flow", bridge, flow]
    raise ValueError(method)


def clear_flows(switches):
    for switch in switches:
        subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "del-flows", switch], check=True, stdout=subprocess.DEVNULL)


def install_all(method, switches, repetition, measured):
    rows = []
    child_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall_start = time.perf_counter_ns()
    for switch in switches:
        for direction, flow in (("forward", "priority=100,in_port=1,actions=output:2"), ("reverse", "priority=100,in_port=2,actions=output:1")):
            start = time.perf_counter_ns()
            result = subprocess.run(command_for(method, switch, flow), text=True, capture_output=True)
            elapsed_us = (time.perf_counter_ns() - start) / 1000.0
            rows.append({
                "evidence_level": "measured_emulation_calibration",
                "switch_count": len(switches),
                "method": method,
                "repetition": repetition,
                "measured": int(measured),
                "switch": switch,
                "direction": direction,
                "latency_us": elapsed_us,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            })
            if result.returncode:
                raise RuntimeError(f"{method} failed on {switch}: {result.stderr}")
    wall_us = (time.perf_counter_ns() - wall_start) / 1000.0
    child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    aggregate = {
        "wall_us": wall_us,
        "child_user_cpu_s": child_after.ru_utime - child_before.ru_utime,
        "child_system_cpu_s": child_after.ru_stime - child_before.ru_stime,
    }
    return rows, aggregate


def run_size(size, config, raw_rows, run_rows):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    net = Mininet(topo=LinearEndpointTopo(switches=size), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    try:
        net.start()
        switches = [f"s{i}" for i in range(1, size + 1)]
        repetitions = config["warmup_repetitions"] + config["measured_repetitions"]
        for rep in range(repetitions):
            measured = rep >= config["warmup_repetitions"]
            methods = list(config["methods"])
            if rep % 2:
                methods.reverse()
            for method in methods:
                clear_flows(switches)
                rss_before = ovs_rss_kib(); mem_before = available_memory_kib()
                rows, aggregate = install_all(method, switches, rep, measured)
                ping_output = net.get("h1").cmd(f"ping -c {config['ping_count_per_repetition']} -W 2 10.0.0.2")
                success = ", 0% packet loss" in ping_output
                raw_rows.extend(rows)
                run_rows.append({
                    "evidence_level": "measured_emulation_calibration",
                    "switch_count": size,
                    "method": method,
                    "repetition": rep,
                    "measured": int(measured),
                    "rules": len(rows),
                    "wall_us": aggregate["wall_us"],
                    "child_user_cpu_s": aggregate["child_user_cpu_s"],
                    "child_system_cpu_s": aggregate["child_system_cpu_s"],
                    "ovs_rss_before_kib": rss_before,
                    "ovs_rss_after_kib": ovs_rss_kib(),
                    "mem_available_before_kib": mem_before,
                    "mem_available_after_kib": available_memory_kib(),
                    "ping_success": int(success),
                })
                if not success:
                    raise RuntimeError(f"ping failed: size={size}, method={method}, rep={rep}: {ping_output}")
    finally:
        net.stop()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def summarise(raw_rows, run_rows):
    output = []
    for size in sorted({row["switch_count"] for row in raw_rows}):
        for method in sorted({row["method"] for row in raw_rows}):
            latency = [row["latency_us"] for row in raw_rows if row["switch_count"] == size and row["method"] == method and row["measured"]]
            runs = [row for row in run_rows if row["switch_count"] == size and row["method"] == method and row["measured"]]
            output.append({
                "switch_count": size,
                "method": method,
                "n_rules": len(latency),
                "n_runs": len(runs),
                "latency_us_mean": statistics.fmean(latency),
                "latency_us_sd": statistics.pstdev(latency),
                "latency_us_p50": percentile(latency, .50),
                "latency_us_p95": percentile(latency, .95),
                "latency_us_p99": percentile(latency, .99),
                "run_wall_ms_mean": statistics.fmean(row["wall_us"] for row in runs) / 1000.0,
                "child_cpu_s_mean": statistics.fmean(row["child_user_cpu_s"] + row["child_system_cpu_s"] for row in runs),
                "ovs_rss_after_kib_mean": statistics.fmean(row["ovs_rss_after_kib"] for row in runs),
                "ping_success_rate": statistics.fmean(row["ping_success"] for row in runs),
            })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=ROOT / "configs/stage2_calibration.json", type=Path)
    parser.add_argument("--output", default=ROOT / "results/stage2_calibration", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not FLOW_CLI.exists():
        raise SystemExit("Build implementation/build/daim_ovs_flow first")
    setLogLevel("warning")
    raw_rows, run_rows = [], []
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for size in config["switch_counts"]:
        run_size(size, config, raw_rows, run_rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "flow_install_raw.csv", raw_rows)
    write_csv(args.output / "run_metrics_raw.csv", run_rows)
    summary = summarise(raw_rows, run_rows)
    write_csv(args.output / "summary.csv", summary)
    metadata = {
        "started_utc": started,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "pass",
        "evidence_level": config["evidence_level"],
        "config": config,
        "raw_rule_rows": len(raw_rows),
        "raw_run_rows": len(run_rows),
        "all_ping_runs_successful": all(row["ping_success"] for row in run_rows),
        "interpretation_warning": config["warning"],
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
