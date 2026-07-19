#!/usr/bin/env python3
"""Stage-2 flow-installation benchmark on real Mininet/Open vSwitch."""

import csv
import json
import os
import resource
import subprocess
import time
from pathlib import Path

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "implementation/build/daim_ovs_flow"
RAW = ROOT / "results/network/stage2_raw.csv"
SIZES = [8, 16, 32, 64]
REPETITIONS = 5


class LinearBenchmarkTopo(Topo):
    def build(self, n):
        switches = [self.addSwitch(f"s{i+1}", protocols="OpenFlow13", failMode="secure") for i in range(n)]
        hosts = [self.addHost(f"h{i+1}", ip=f"10.0.0.{i+1}/24") for i in range(n)]
        for switch, host in zip(switches, hosts): self.addLink(host, switch)
        for left, right in zip(switches, switches[1:]): self.addLink(left, right)


def host_metrics():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = getattr(usage, "ru_maxrss", 0)
    # Linux reports KiB; macOS reports bytes. The benchmark runs in Linux.
    return {"python_user_cpu_s": usage.ru_utime, "python_system_cpu_s": usage.ru_stime, "python_max_rss_kib": rss_kb}


def install(bridge, flow):
    start = time.perf_counter_ns()
    result = subprocess.run([str(CLI), "add", bridge, flow], text=True, capture_output=True)
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    if result.returncode:
        raise RuntimeError(f"flow install failed for {bridge}: {result.stderr}")
    return elapsed_us


def run_size(size, repetition):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    net = Mininet(topo=LinearBenchmarkTopo(n=size), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    row = {"evidence_level": "measured_emulation", "network_size": size, "repetition": repetition}
    try:
        net.start()
        warmup = []
        samples = []
        for i in range(size):
            flow = "priority=100,ip,actions=normal"
            samples.append(install(f"s{i+1}", flow))
            warmup.append(i + 1)
        h1, hn = net.get("h1", f"h{size}")
        ping = h1.cmd(f"ping -c 3 -W 1 10.0.0.{size}")
        row.update({
            "flow_count": len(samples),
            "install_sum_us": sum(samples),
            "install_min_us": min(samples),
            "install_max_us": max(samples),
            "install_mean_us": sum(samples) / len(samples),
            "ping_success": int("0% packet loss" in ping),
            **host_metrics(),
        })
    finally:
        net.stop()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return row


def main():
    if not CLI.exists(): raise SystemExit(f"missing {CLI}; run make in implementation")
    setLogLevel("warning")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for size in SIZES:
        for repetition in range(1, REPETITIONS + 1):
            print(f"stage2 size={size} repetition={repetition}", flush=True)
            rows.append(run_size(size, repetition))
    with RAW.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"evidence_level":"measured_emulation", "rows":len(rows), "raw":str(RAW)}, indent=2))


if __name__ == "__main__": main()

