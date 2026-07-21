#!/usr/bin/env python3
"""Stage-2 four-way comparison, extending the original DAIM-adapter-vs-
direct-ovs-ofctl benchmark with two more paths requested by the TNSM
review, so process-spawn cost, DAIM Core/ctypes cost, and native-controller
OpenFlow cost are no longer confounded:

  daim_process_per_rule  -- existing DAIM C adapter, spawns ovs-ofctl per rule
  daim_persistent        -- new DAIM C adapter, one persistent OpenFlow
                             connection per switch, raw Flow-Mod, no subprocess
  direct_ovs_cli         -- existing baseline, spawns ovs-ofctl directly
  direct_osken           -- a plain Os-Ken controller with no DAIM
                             involvement at all, confirmed via Barrier Reply

Same linear topology, same one-rule-per-switch workload, same sizes and
repetition count as the original comparison, for a like-for-like extension.
"""
import csv
import json
import resource
import threading
import subprocess
import time
from pathlib import Path

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "implementation/build/daim_ovs_flow"
PERSISTENT_CLI = ROOT / "implementation/build/daim_persistent_flow"
DIRECT_OSKEN_APP = ROOT / "network/osken_direct_baseline_controller.py"
RAW = ROOT / "results/network/stage2_full_compare_raw.csv"
SIZES = [8, 16, 32, 64]
REPETITIONS = 5
PERSISTENT_BASE_PORT = 17000
FLOW = "priority=100,ip,actions=normal"


class LinearBenchmarkTopo(Topo):
    def build(self, n):
        switches = [self.addSwitch(f"s{i+1}", protocols="OpenFlow13", failMode="secure") for i in range(n)]
        hosts = [self.addHost(f"h{i+1}", ip=f"10.0.0.{i+1}/24") for i in range(n)]
        for switch, host in zip(switches, hosts):
            self.addLink(host, switch)
        for left, right in zip(switches, switches[1:]):
            self.addLink(left, right)


def install_cli(argv):
    start = time.perf_counter_ns()
    result = subprocess.run(argv, text=True, capture_output=True)
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    if result.returncode:
        raise RuntimeError(f"{argv}: {result.stderr}")
    return elapsed_us


def summarise(mode, size, repetition, samples, ping_output, usage):
    return {
        "evidence_level": "measured_emulation",
        "mode": mode,
        "network_size": size,
        "repetition": repetition,
        "flow_count": len(samples),
        "install_sum_us": sum(samples),
        "install_mean_us": sum(samples) / len(samples),
        "ping_success": int("0% packet loss" in ping_output),
        "python_cpu_s": usage.ru_utime + usage.ru_stime,
        "python_max_rss_kib": usage.ru_maxrss,
    }


def install_persistent(bridge, port):
    """Starts the listener before pointing the bridge at it, so OVS's first
    connection attempt succeeds immediately instead of hitting its
    reconnect-backoff after an initial refused connection -- confirmed by a
    ~1s-per-switch inflation when the controller target was set first."""
    proc = subprocess.Popen(
        [str(PERSISTENT_CLI), bridge, str(port), FLOW, "10"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(0.05)  # let the listener reach accept() before OVS connects
    start = time.perf_counter_ns()
    subprocess.run(["ovs-vsctl", "set-controller", bridge, f"tcp:127.0.0.1:{port}"], check=True)
    _, stderr = proc.communicate(timeout=15)
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    if proc.returncode != 0:
        raise RuntimeError(f"daim_persistent_flow failed for {bridge}: {stderr}")
    return elapsed_us


def run_cli_mode(mode, size, repetition):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    net = Mininet(topo=LinearBenchmarkTopo(n=size), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    try:
        net.start()
        samples = []
        for i in range(size):
            bridge = f"s{i+1}"
            if mode == "daim_persistent":
                samples.append(install_persistent(bridge, PERSISTENT_BASE_PORT + i))
                continue
            if mode == "daim_process_per_rule":
                argv = [str(CLI), "add", bridge, FLOW]
            elif mode == "direct_ovs_cli":
                argv = ["ovs-ofctl", "-O", "OpenFlow13", "add-flow", bridge, FLOW]
            else:
                raise ValueError(mode)
            samples.append(install_cli(argv))
        h1, hn = net.get("h1", f"h{size}")
        ping = h1.cmd(f"ping -c 3 -W 1 10.0.0.{size}")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return summarise(mode, size, repetition, samples, ping, usage)
    finally:
        net.stop()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_direct_osken(size, repetition):
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Defensive: a stale instance of this exact controller still holding
    # port 6653 (e.g. from an abnormally killed prior run, which bypasses
    # the finally-block cleanup below) causes new switch connections to be
    # load-balanced across multiple listeners unpredictably, silently
    # starving this run's own stdout read. Confirmed during development.
    subprocess.run(["pkill", "-9", "-f", str(DIRECT_OSKEN_APP)], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    controller = subprocess.Popen(
        ["osken-manager", str(DIRECT_OSKEN_APP), "--ofp-tcp-listen-port", "6653"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    net = None
    watchdog = None
    try:
        time.sleep(1.5)
        net = Mininet(
            topo=LinearBenchmarkTopo(n=size),
            controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
            switch=OVSSwitch, link=TCLink, autoSetMacs=True,
        )
        net.start()

        # Blocking readline() in a loop, not select(): select() reports
        # readiness at the OS file-descriptor level, but Python's buffered
        # TextIOWrapper can pull several already-flushed lines into its own
        # userspace buffer in a single underlying read() syscall. Once that
        # happens, select() correctly reports "nothing new at the OS level"
        # even though readline() would return instantly from the buffer --
        # so a select-gated loop can spin forever after the first burst.
        # Confirmed during development: flows were installed and confirmed
        # (visible via dump-flows) while the select-based reader still
        # reported no data. A watchdog thread bounds the blocking read.
        watchdog_fired = threading.Event()

        def kill_after_timeout():
            if not watchdog_fired.wait(90):
                controller.kill()

        watchdog = threading.Thread(target=kill_after_timeout, daemon=True)
        watchdog.start()

        samples = []
        while len(samples) < size:
            line = controller.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "flow_confirmed":
                samples.append(event["elapsed_us"])
        watchdog_fired.set()
        if len(samples) != size:
            raise RuntimeError(f"only {len(samples)}/{size} switches confirmed a Flow-Mod")

        h1, hn = net.get("h1", f"h{size}")
        ping = h1.cmd(f"ping -c 3 -W 1 10.0.0.{size}")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return summarise("direct_osken", size, repetition, samples, ping, usage)
    finally:
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
    for mode in ("daim_process_per_rule", "daim_persistent", "direct_ovs_cli"):
        for size in SIZES:
            for repetition in range(1, REPETITIONS + 1):
                print(f"mode={mode} size={size} repetition={repetition}", flush=True)
                rows.append(run_cli_mode(mode, size, repetition))
    for size in SIZES:
        for repetition in range(1, REPETITIONS + 1):
            print(f"mode=direct_osken size={size} repetition={repetition}", flush=True)
            rows.append(run_direct_osken(size, repetition))

    with RAW.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {RAW}")


if __name__ == "__main__":
    main()
