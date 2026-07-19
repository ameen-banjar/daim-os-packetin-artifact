#!/usr/bin/env python3
"""Stage-2 matched comparison: DAIM C adapter versus direct ovs-ofctl."""

import csv
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
RAW = ROOT / "results/network/stage2_baseline_raw.csv"
SIZES = [8, 16, 32, 64]
REPETITIONS = 5


class LinearBenchmarkTopo(Topo):
    def build(self, n):
        switches = [self.addSwitch(f"s{i+1}", protocols="OpenFlow13", failMode="secure") for i in range(n)]
        hosts = [self.addHost(f"h{i+1}", ip=f"10.0.0.{i+1}/24") for i in range(n)]
        for switch, host in zip(switches, hosts): self.addLink(host, switch)
        for left, right in zip(switches, switches[1:]): self.addLink(left, right)


def install(mode, bridge, flow):
    if mode == "daim_adapter":
        argv = [str(CLI), "add", bridge, flow]
    else:
        argv = ["ovs-ofctl", "-O", "OpenFlow13", "add-flow", bridge, flow]
    start = time.perf_counter_ns()
    result = subprocess.run(argv, text=True, capture_output=True)
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    if result.returncode: raise RuntimeError(f"{mode} failed for {bridge}: {result.stderr}")
    return elapsed_us


def run_one(size, repetition, mode):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    net = Mininet(topo=LinearBenchmarkTopo(n=size), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    try:
        net.start(); samples = [install(mode, f"s{i+1}", "priority=100,ip,actions=normal") for i in range(size)]
        h1, hn = net.get("h1", f"h{size}")
        ping = h1.cmd(f"ping -c 3 -W 1 10.0.0.{size}")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {"evidence_level":"measured_emulation", "mode":mode, "network_size":size, "repetition":repetition, "flow_count":len(samples), "install_sum_us":sum(samples), "install_mean_us":sum(samples)/len(samples), "ping_success":int("0% packet loss" in ping), "python_cpu_s":usage.ru_utime+usage.ru_stime, "python_max_rss_kib":usage.ru_maxrss}
    finally:
        net.stop(); subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    setLogLevel("warning"); RAW.parent.mkdir(parents=True, exist_ok=True); rows=[]
    for mode in ("daim_adapter", "direct_ovs"):
        for size in SIZES:
            for repetition in range(1, REPETITIONS+1):
                print(f"baseline mode={mode} size={size} repetition={repetition}", flush=True)
                rows.append(run_one(size,repetition,mode))
    with RAW.open("w", newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {RAW}")


if __name__ == "__main__": main()

