#!/usr/bin/env python3
"""Real Mininet/OVS smoke test driven by the DAIM OVS adapter CLI."""

import json
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


class TwoSwitchTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
        s2 = self.addSwitch("s2", protocols="OpenFlow13", failMode="secure")
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s2, h2)


def install(bridge, flow):
    start = time.perf_counter_ns()
    result = subprocess.run([str(FLOW_CLI), "add", bridge, flow], text=True, capture_output=True)
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    if result.returncode:
        raise RuntimeError(f"flow install failed: {result.stderr}")
    return elapsed_us


def main():
    if not FLOW_CLI.exists():
        raise SystemExit(f"missing {FLOW_CLI}; run make in implementation")
    setLogLevel("warning")
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    net = Mininet(topo=TwoSwitchTopo(), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    evidence = {"evidence_level": "measured_emulation", "topology": "2 switches, 2 hosts", "flows": []}
    try:
        net.start()
        # Mininet assigns: s1-eth1=h1, s1-eth2=s2, s2-eth1=s1, s2-eth2=h2.
        flows = [
            ("s1", "priority=100,in_port=1,actions=output:2"),
            ("s1", "priority=100,in_port=2,actions=output:1"),
            ("s2", "priority=100,in_port=1,actions=output:2"),
            ("s2", "priority=100,in_port=2,actions=output:1"),
        ]
        for bridge, flow in flows:
            evidence["flows"].append({"bridge": bridge, "flow": flow, "install_us_host_clock": install(bridge, flow)})
        h1, h2 = net.get("h1", "h2")
        ping_output = h1.cmd("ping -c 5 -W 1 10.0.0.2")
        evidence["ping_output"] = ping_output
        evidence["ping_success"] = ", 0% packet loss" in ping_output
        evidence["s1_flows"] = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"], text=True, capture_output=True, check=True).stdout
        evidence["s2_flows"] = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s2"], text=True, capture_output=True, check=True).stdout
    finally:
        net.stop()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(json.dumps(evidence, indent=2))
    if not evidence.get("ping_success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
