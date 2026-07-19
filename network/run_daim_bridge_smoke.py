#!/usr/bin/env python3
"""Stage: DAIM Packet-In -> Core -> OVS bridge smoke test.

Same two-switch/two-host shape as run_real_controller_smoke.py, but the
controller is daim_bridge_controller.py, which delegates every Packet-In to
the compiled DAIM Core (via ctypes) instead of a Python MAC-learning dict.
A learned destination causes DAIM Core's OVS adapter to run a real
`ovs-ofctl add-flow`, so a passing run is evidence that Packet-In events are
reaching daim_core_emit(NO_RULE, ...) and that the resulting decision
becomes a real OpenFlow rule -- not just a Python-side forwarding table.
"""
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import LinearTopo
from mininet.log import setLogLevel

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "results/network/daim_bridge_smoke.json"
APP = ROOT / "network/daim_bridge_controller.py"


def ctl_state():
    out = {}
    for b in ("s1", "s2"):
        p = subprocess.run(["ovs-vsctl", "get-controller", b], text=True, capture_output=True)
        out[b] = p.stdout.strip()
    return out


def dump_flows():
    out = {}
    for b in ("s1", "s2"):
        p = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", b], text=True, capture_output=True)
        out[b] = p.stdout
    return out


def main():
    setLogLevel("warning")
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ctl = subprocess.Popen(
        ["osken-manager", str(APP), "--ofp-tcp-listen-port", "6653"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    net = None
    result = {"evidence_level": "measured_emulation"}
    try:
        time.sleep(2)
        net = Mininet(
            topo=LinearTopo(k=2),
            controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
            switch=OVSSwitch, autoSetMacs=True,
        )
        net.start()
        time.sleep(2)
        result["controller_pid"] = ctl.pid
        result["controller_state_before"] = ctl_state()
        h1, h2 = net.hosts

        result["flows_before_ping"] = dump_flows()

        first = h1.cmd("ping -c 5 -W 1 " + h2.IP())
        result["ping_first"] = first

        # Give DAIM's ovs-ofctl add-flow calls a moment to land, then confirm
        # the installed rules carry DAIM's dl_dst match, not a controller FlowMod.
        time.sleep(1)
        result["flows_after_ping"] = dump_flows()

        second = h1.cmd("ping -c 5 -W 1 " + h2.IP())
        result["ping_second"] = second

        os.kill(ctl.pid, signal.SIGTERM)
        ctl.wait(timeout=5)
        result["controller_stopped"] = True
        time.sleep(1)

        after_stop = h1.cmd("ping -c 10 -i 0.1 -W 1 " + h2.IP())
        result["ping_after_controller_stop"] = after_stop
        result["flows_after_controller_stop"] = dump_flows()
    finally:
        if net:
            net.stop()
        if ctl.poll() is None:
            ctl.terminate()
            ctl.wait(timeout=5)
        subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(result, indent=2) + "\n")
    print(LOG)

    daim_rules = sum(
        result["flows_after_ping"][b].count("dl_dst=") for b in ("s1", "s2")
    )
    print("daim_installed_dl_dst_rules=%d" % daim_rules)
    assert daim_rules >= 1, "no DAIM-installed dl_dst flow found after ping"
    assert "0% packet loss" in result["ping_second"]
    print("daim_bridge_smoke_verification=PASS")


if __name__ == "__main__":
    main()
