#!/usr/bin/env python3
"""Sustained-load resource and control-traffic profile for the reactive
Packet-In path, complementing packetin_latency_breakdown.py (single-event
per-stage latency) and stage2_full_compare.py (proactive rule install).
Neither existing experiment reports throughput under sustained arrivals,
controller-process CPU/memory, or control-channel bytes -- gaps named in
task #18 of the TNSM revision plan.

One switch, 43 hosts: h1 the shared, primed destination; h2 the primer;
h3..h42 as 40 distinct senders; h43 a dedicated signal host. Per
repetition, within a single controller/topology lifetime (no teardown
between sends, unlike the latency-breakdown experiment, so this measures
sustained load rather than repeated cold starts):

  1. h2 pings h1 once, untimed -- teaches DAIM Core h1's (mac, port).
  2. h3..h42 each ping h1 once, back-to-back. Each sender's first frame on
     its switch port is a genuine NO_RULE event (unlearned source), so this
     is 40 real reactive decisions per repetition, not a synthetic loop.
  3. h43 pings h1 once, as an explicit end-of-window marker.

A fixed NO_RULE-event-count threshold was tried first and rejected: each
real ping's ARP request/reply and ICMP request/reply each independently
generate a NO_RULE event only if that specific (in_port, dl_dst) direction
has no flow installed yet, which depends on prior traffic in a way that
cannot be predicted from N_SENDERS alone. A dedicated signal host sourcing
one identifiable packet after all real sends have gone through sidesteps
that: daim_bridge_controller.py (DAIM_LOAD_PROFILE_SIGNAL_IP=h43's IP)
reports one {"event": "load_profile", ...} line as soon as it sees a
packet sourced from h43, containing:
  - throughput_installs_per_s: flows_installed / wall-clock seconds elapsed
    since the controller became ready (not since repetition start, so
    controller/switch-connection setup is excluded).
  - cpu_s / max_rss_kib: resource.getrusage(RUSAGE_SELF) delta for the
    controller process, which also hosts DAIM Core in-process via ctypes.
  - control_bytes_total / control_messages_total: for mode=persistent,
    the adapter's own real send() byte/message counters
    (ovs_persistent_adapter.c); for mode=process_per_rule, which has no
    persistent channel to instrument, flows_installed times the exact
    OpenFlow 1.3 Flow-Mod wire size computed by the same encoder
    (daim_ovs_wire_flow_mod_size) -- labelled control_bytes_source so the
    two are never conflated in analysis.

ovs-vswitchd's own CPU/RSS (a separate OS process, outside the
controller) is sampled before and after each repetition via /proc, since
that cost is shared across all four southbound paths in this artifact and
attributing it to any one adapter mode would overclaim.
"""
import csv
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_APP = ROOT / "network/daim_bridge_controller.py"
RAW = ROOT / "results/network/control_plane_load_profile_raw.csv"
MODES = ["process_per_rule", "persistent"]
REPETITIONS = 30
N_SENDERS = 40
N_HOSTS = N_SENDERS + 3  # h1 destination, h2 primer, ..., last host is the signal marker
OFP_PORT = 6653
PERSISTENT_BASE_PORT = 17400
READY_TIMEOUT_S = 20
LOAD_PROFILE_TIMEOUT_S = 60
DEST_IP = "10.0.0.1"


class SingleSwitchFanoutTopo(Topo):
    def build(self, n_hosts):
        switch = self.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
        for i in range(1, n_hosts + 1):
            host = self.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
            self.addLink(host, switch)


def read_json_lines_until(proc, watchdog_fired, predicate, timeout_s):
    """Blocking readline() loop bounded by a watchdog thread, matching the
    approach documented in stage2_full_compare.py's run_direct_osken."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if predicate(event):
            return event
    return None


def ovs_vswitchd_usage():
    pid = subprocess.run(["pidof", "ovs-vswitchd"], capture_output=True, text=True).stdout.strip()
    if not pid:
        return None
    out = subprocess.run(
        ["ps", "-o", "cputime=,rss=", "-p", pid], capture_output=True, text=True
    ).stdout.strip()
    if not out:
        return None
    cputime, rss_kib = out.split()
    h, m, s = (["0"] * (3 - len(cputime.split(":")))) + cputime.split(":")
    return {"cpu_s": int(h) * 3600 + int(m) * 60 + float(s), "rss_kib": int(rss_kib)}


def run_trial(mode, repetition, persistent_port):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", str(CONTROLLER_APP)], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.2)

    signal_ip = f"10.0.0.{N_HOSTS}"
    env = dict(os.environ)
    env["DAIM_ADAPTER_MODE"] = mode
    env["DAIM_LOAD_PROFILE_SIGNAL_IP"] = signal_ip
    if mode == "persistent":
        env["DAIM_PERSISTENT_PORT"] = str(persistent_port)

    controller = subprocess.Popen(
        ["osken-manager", str(CONTROLLER_APP), "--ofp-tcp-listen-port", str(OFP_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env,
    )
    net = None
    watchdog_fired = threading.Event()

    def kill_after_timeout():
        if not watchdog_fired.wait(READY_TIMEOUT_S + LOAD_PROFILE_TIMEOUT_S + 15):
            controller.kill()

    watchdog = threading.Thread(target=kill_after_timeout, daemon=True)
    watchdog.start()

    try:
        net = Mininet(topo=SingleSwitchFanoutTopo(n_hosts=N_HOSTS), controller=None,
                       switch=OVSSwitch, link=TCLink, autoSetMacs=True)
        net.start()

        controller_targets = [f"tcp:127.0.0.1:{OFP_PORT}"]
        if mode == "persistent":
            controller_targets.append(f"tcp:127.0.0.1:{persistent_port}")
        subprocess.run(["ovs-vsctl", "set-controller", "s1", *controller_targets], check=True)

        ready = read_json_lines_until(
            controller, watchdog_fired,
            lambda e: e.get("event") in ("ready", "adapter_error"),
            READY_TIMEOUT_S,
        )
        if ready is None:
            raise RuntimeError(f"{mode} rep {repetition}: controller never became ready")
        if ready.get("event") == "adapter_error":
            raise RuntimeError(f"{mode} rep {repetition}: adapter_error: {ready.get('detail')}")
        time.sleep(0.15)

        ovs_before = ovs_vswitchd_usage()

        hosts = net.get(*[f"h{i}" for i in range(1, N_HOSTS + 1)])
        senders, signal_host = hosts[2:-1], hosts[-1]
        prime = hosts[1].cmd(f"ping -c 1 -W 1 {DEST_IP}")
        prime_ok = "0% packet loss" in prime

        ping_results = []
        for sender in senders:
            out = sender.cmd(f"ping -c 1 -W 1 {DEST_IP}")
            ping_results.append("0% packet loss" in out)

        signal_ping = signal_host.cmd(f"ping -c 1 -W 1 {DEST_IP}")
        signal_ok = "0% packet loss" in signal_ping

        profile = read_json_lines_until(
            controller, watchdog_fired, lambda e: e.get("event") == "load_profile",
            LOAD_PROFILE_TIMEOUT_S,
        )
        watchdog_fired.set()
        if profile is None:
            raise RuntimeError(f"{mode} rep {repetition}: no load_profile event reported "
                                f"({sum(ping_results)}/{len(ping_results)} sender pings succeeded, "
                                f"signal_ok={signal_ok})")

        ovs_after = ovs_vswitchd_usage()

        row = {
            "mode": mode,
            "repetition": repetition,
            "evidence_level": "measured_emulation",
            "n_senders": len(senders),
            "priming_ok": int(bool(prime_ok)),
            "signal_ok": int(bool(signal_ok)),
            "pings_succeeded": sum(ping_results),
            "pings_attempted": len(ping_results),
        }
        row.update({k: v for k, v in profile.items() if k != "event"})
        if ovs_before and ovs_after:
            row["ovs_vswitchd_cpu_s_delta"] = ovs_after["cpu_s"] - ovs_before["cpu_s"]
            row["ovs_vswitchd_rss_kib_after"] = ovs_after["rss_kib"]
        else:
            row["ovs_vswitchd_cpu_s_delta"] = None
            row["ovs_vswitchd_rss_kib_after"] = None
        return row
    finally:
        watchdog_fired.set()
        if net:
            net.stop()
        if controller.poll() is None:
            controller.terminate()
            try:
                controller.wait(timeout=5)
            except subprocess.TimeoutExpired:
                controller.kill()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    setLogLevel("warning")
    RAW.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    persistent_port_counter = 0
    for mode in MODES:
        for repetition in range(1, REPETITIONS + 1):
            persistent_port = None
            if mode == "persistent":
                persistent_port = PERSISTENT_BASE_PORT + persistent_port_counter
                persistent_port_counter += 1
            print(f"mode={mode} repetition={repetition}", flush=True)
            rows.append(run_trial(mode, repetition, persistent_port))

    fieldnames = list(rows[0])
    with RAW.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {RAW}")


if __name__ == "__main__":
    main()
