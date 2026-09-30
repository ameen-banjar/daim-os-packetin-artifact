#!/usr/bin/env python3
"""One-off diagnostic: why did Q2 (new flow during controller downtime)
report success? Prints raw ping output and controller connection state."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_APP = ROOT / "network/daim_bridge_controller.py"
OFP_PORT = 6653
PERSISTENT_PORT = 17301
H1_IP, H2_IP, H3_IP = "10.0.0.1", "10.0.0.2", "10.0.0.3"


class T(Topo):
    def build(self):
        s = self.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
        for h, ip in (("h1", H1_IP), ("h2", H2_IP), ("h3", H3_IP)):
            self.addHost(h, ip=f"{ip}/24")
            self.addLink(h, s)


def main():
    setLogLevel("warning")
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = dict(os.environ)
    env["DAIM_ADAPTER_MODE"] = "persistent"
    env["DAIM_TARGET_IP"] = H2_IP
    env["DAIM_PERSISTENT_PORT"] = str(PERSISTENT_PORT)
    ctl = subprocess.Popen(["osken-manager", str(CONTROLLER_APP), "--ofp-tcp-listen-port", str(OFP_PORT)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
    net = Mininet(topo=T(), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    try:
        net.start()
        subprocess.run(["ovs-vsctl", "set-controller", "s1", f"tcp:127.0.0.1:{OFP_PORT}", f"tcp:127.0.0.1:{PERSISTENT_PORT}"], check=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            line = ctl.stdout.readline()
            if not line:
                break
            try:
                e = json.loads(line.strip())
            except Exception:
                continue
            if e.get("event") == "ready":
                break
        time.sleep(0.15)
        h1, h2, h3 = net.get("h1", "h2", "h3")
        h3.cmd(f"ping -c 2 -W 1 {H2_IP}")
        print("SETUP h1->h2:", h1.cmd(f"ping -c 1 -W 1 {H2_IP}"))

        print("=== ovs-vsctl show before stop ===")
        print(subprocess.run(["ovs-vsctl", "show"], text=True, capture_output=True).stdout)

        os.kill(ctl.pid, signal.SIGTERM)
        ctl.wait(timeout=5)
        time.sleep(0.5)

        print("=== ovs-vsctl show after stop (controller state) ===")
        print(subprocess.run(["ovs-vsctl", "show"], text=True, capture_output=True).stdout)
        print("=== fail-mode ===")
        print(subprocess.run(["ovs-vsctl", "get-fail-mode", "s1"], text=True, capture_output=True).stdout)
        print("=== is_connected ===")
        print(subprocess.run(["ovs-vsctl", "wait-until", "Controller", ".", "connected=false", "--", "list", "Controller"],
                              text=True, capture_output=True).stdout)

        print("=== RAW ping h1->h3 during downtime (new flow) ===")
        print(h1.cmd(f"ping -c 3 -W 1 {H3_IP}"))

        print("=== dump-flows after Q2 ping ===")
        print(subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"], text=True, capture_output=True).stdout)

        print("=== arp -n on h1 ===")
        print(h1.cmd("arp -n"))
    finally:
        net.stop()
        if ctl.poll() is None:
            ctl.terminate()
        subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
