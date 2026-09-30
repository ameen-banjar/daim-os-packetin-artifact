#!/usr/bin/env python3
"""R5 controller-restart-recovery protocol
(01_DAIM_OS_Implementation/R5_RESTART_RECOVERY_PROTOCOL.md), limited-check
mode: ONE trial per arm, run after the second round of fixes below, kept
separate from the official 60-trial sample (r5_restart_recovery_official.py).

Reuses packetin_latency_breakdown.py's controller apps unchanged, on a
four-host variant of its topology (h1-h4) so the "new flow" pairs tested
in Q2 and Q3 are genuinely distinct from each other and from anything
warm-up/setup already taught the controller -- not reused, and not
merely asserted distinct.
"""
import json
import os
import re
import selectors
import signal
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_APP = ROOT / "network/daim_bridge_controller.py"
REACTIVE_BASELINE_APP = ROOT / "network/osken_reactive_baseline_controller.py"
OFP_PORT = 6653
PERSISTENT_PORT = 17300
READY_TIMEOUT_S = 20
RECOVER_WINDOW_S = 15  # feasibility default; the official run uses 30s (protocol change, documented)
H_IPS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}
H_MACS = {"h1": "00:00:00:00:00:01", "h2": "00:00:00:00:00:02",
          "h3": "00:00:00:00:00:03", "h4": "00:00:00:00:00:04"}
H_PORTS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}  # Mininet's link-order port assignment


# ---------------------------------------------------------------------------
# Ping-result parsing. History: a plain `"0% packet loss" in out` substring
# check is true for "100% packet loss" too (round 1 bug). Round 2 review
# found the fixed version still treated an RC/count disagreement, or a
# missing RC marker, as merely "not ok" rather than a tool-measurement
# error -- both are now `valid=False` (an instrumentation-error state),
# not a trustworthy service-failure observation.
# ---------------------------------------------------------------------------
COUNTS_RE = re.compile(r"(\d+) packets transmitted, (\d+) (?:packets )?received")
RC_RE = re.compile(r"RC=(-?\d+)\s*$")


def parse_ping_output(text):
    """Pure function, no Mininet/network dependency -- unit-testable
    standalone. Returns a dict: valid, ok, transmitted, received, rc,
    parse_error. `valid=False` always means "do not trust `ok`, this was
    a measurement-tool problem", never a service observation."""
    result = {"valid": False, "ok": False, "transmitted": None, "received": None,
              "rc": None, "parse_error": None, "raw": text}
    if not text or not text.strip():
        result["parse_error"] = "empty_output"
        return result
    rc_match = RC_RE.search(text)
    if not rc_match:
        result["parse_error"] = "missing_rc_marker"
        return result
    result["rc"] = int(rc_match.group(1))
    counts_match = COUNTS_RE.search(text)
    if not counts_match:
        result["parse_error"] = "no_counts_match"
        return result
    transmitted, received = int(counts_match.group(1)), int(counts_match.group(2))
    result["transmitted"] = transmitted
    result["received"] = received
    if transmitted <= 0:
        result["parse_error"] = "zero_transmitted"
        return result
    counts_say_ok = received >= transmitted
    rc_says_ok = result["rc"] == 0
    if rc_says_ok != counts_say_ok:
        result["parse_error"] = f"rc_counts_disagree(rc={result['rc']},tx={transmitted},rx={received})"
        return result  # valid stays False: this is a tool-disagreement error, not a service result
    result["valid"] = True
    result["ok"] = counts_say_ok
    return result


def _self_test_parser():
    """Run before every use of this script -- see also
    r5_ping_parser_selftest.py for the standalone version executed
    locally (no VM) during the fix review."""
    cases = [
        ("full success", "PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.\r\n64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.366 ms\r\n\r\n--- 10.0.0.2 ping statistics ---\r\n1 packets transmitted, 1 received, 0% packet loss, time 0ms\r\nrtt min/avg/max/mdev = 0.366/0.366/0.366/0.000 ms\r\nRC=0\n", True),
        ("complete loss", "PING 10.0.0.3 (10.0.0.3) 56(84) bytes of data.\r\n\r\n--- 10.0.0.3 ping statistics ---\r\n1 packets transmitted, 0 received, 100% packet loss, time 0ms\r\n\r\nRC=1\n", False),
        ("complete loss with host unreachable", "PING 10.0.0.3 (10.0.0.3) 56(84) bytes of data.\r\nFrom 10.0.0.1 icmp_seq=1 Destination Host Unreachable\r\n\r\n--- 10.0.0.3 ping statistics ---\r\n1 packets transmitted, 0 received, +1 errors, 100% packet loss, time 0ms\r\n\r\nRC=1\n", False),
        ("partial loss, count=5", "PING x\r\n\r\n--- x ping statistics ---\r\n5 packets transmitted, 3 received, 40% packet loss, time 400ms\r\n\r\nRC=1\n", False),
        ("partial loss, count=5, 1 received", "PING x\r\n\r\n--- x ping statistics ---\r\n5 packets transmitted, 1 received, 80% packet loss, time 400ms\r\n\r\nRC=1\n", False),
        ("decimal percentage success", "PING x\r\n\r\n--- x ping statistics ---\r\n1 packets transmitted, 1 received, 0.0% packet loss, time 0ms\r\n\r\nRC=0\n", True),
        ("decimal percentage total loss", "PING x\r\n\r\n--- x ping statistics ---\r\n1 packets transmitted, 0 received, 100.0% packet loss, time 0ms\r\n\r\nRC=1\n", False),
        ("empty output", "", None),
        ("garbage/error output", "bash: ping: command not found\r\n", None),
        ("truncated output mid-line", "PING 10.0.0.2 (10.0.0.2) 56(84) by", None),
        ("missing RC marker -- now an error, not silently trusted", "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n", None),
        ("rc/count disagreement -- now invalid, not just not-ok", "1 packets transmitted, 0 received, 100% packet loss, time 0ms\r\nRC=0\n", None),
    ]
    failures = []
    for name, text, expected_ok in cases:
        r = parse_ping_output(text)
        if expected_ok is None:
            if r["valid"]:
                failures.append(f"{name}: expected invalid/unparseable, got valid=True ok={r['ok']}")
        else:
            if not r["valid"] or r["ok"] != expected_ok:
                failures.append(f"{name}: expected ok={expected_ok}, got valid={r['valid']} ok={r['ok']} err={r['parse_error']}")
    if failures:
        raise AssertionError("ping parser self-test failed:\n" + "\n".join(failures))


def cmd_ping(host, target_ip, count=1, wait_s=1):
    """Runs ping via host.cmd(), appending an RC marker, and parses the
    result through parse_ping_output(). Returns the parsed dict plus
    t_start/t_end (monotonic) bracketing the whole call."""
    t_start = time.monotonic()
    out = host.cmd(f"ping -c {count} -W {wait_s} {target_ip}; echo RC=$?")
    t_end = time.monotonic()
    r = parse_ping_output(out)
    r["t_start"] = t_start
    r["t_end"] = t_end
    return r


def dump_flows():
    """Returns stdout/stderr/rc explicitly -- a non-zero exit means the
    tool itself failed (e.g. ovs-ofctl/bridge problem), which must not be
    read as "no matching rule": that is a measurement error, not a
    negative observation."""
    p = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"],
                        text=True, capture_output=True)
    return {"stdout": p.stdout, "stderr": p.stderr, "rc": p.returncode,
            "tool_error": p.returncode != 0}


def flow_status(flows, in_port, dst_mac, expected_out_port):
    """Checks both that a rule matching (in_port, dl_dst) exists AND that
    its action is the expected output port -- the earlier version only
    checked the match, not the action. Returns a dict distinguishing
    tool_error from a genuine present/absent/wrong-action reading."""
    if flows["tool_error"]:
        return {"tool_error": True, "exists": None, "correct_action": None}
    pattern = re.compile(
        r"in_port=" + str(in_port) + r"[,\s].*dl_dst=" + re.escape(dst_mac) +
        r".*actions=([^\s]+)"
    )
    m = pattern.search(flows["stdout"])
    if not m:
        return {"tool_error": False, "exists": False, "correct_action": None}
    action = m.group(1)
    return {"tool_error": False, "exists": True, "correct_action": action == f"output:{expected_out_port}",
            "action_seen": action}


# ---------------------------------------------------------------------------
# Bounded-wait line reader. The previous version used select() once, then
# a plain blocking readline() -- select() only guarantees bytes are
# available, not that a full line is available, so a stalled partial line
# could still block past the deadline. This buffers raw non-blocking reads
# and only ever yields a complete line, always re-checking the deadline.
# ---------------------------------------------------------------------------
class BoundedLineReader:
    def __init__(self, fileobj):
        self.fd = fileobj.fileno()
        os.set_blocking(self.fd, False)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.fd, selectors.EVENT_READ)
        self.buf = b""

    def readline(self, deadline_monotonic):
        while b"\n" not in self.buf:
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                return None, "timeout"
            events = self.sel.select(timeout=max(0, remaining))
            if not events:
                continue  # re-check deadline
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if chunk == b"":
                if self.buf:
                    line, self.buf = self.buf, b""
                    return line.decode(errors="replace"), None
                return None, "stream_closed"
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        return line.decode(errors="replace"), None

    def close(self):
        try:
            self.sel.unregister(self.fd)
        except Exception:
            pass
        self.sel.close()


def read_until_ready(reader, deadline_monotonic, events_out=None):
    while True:
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            return None, "timeout"
        line, err = reader.readline(deadline_monotonic)
        if line is None:
            return None, err
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if events_out is not None:
                events_out.append({"raw": line})
            continue
        if events_out is not None:
            events_out.append(event)
        if event.get("event") in ("ready", "adapter_error"):
            return event, None


def launch_controller(mode):
    env = dict(os.environ)
    env["DAIM_ADAPTER_MODE"] = "persistent"
    env["DAIM_TARGET_IP"] = H_IPS["h2"]
    if mode == "persistent":
        env["DAIM_PERSISTENT_PORT"] = str(PERSISTENT_PORT)
    app = REACTIVE_BASELINE_APP if mode == "reactive_osken" else CONTROLLER_APP
    proc = subprocess.Popen(
        ["osken-manager", str(app), "--ofp-tcp-listen-port", str(OFP_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env,
    )
    return proc


def run_trial(mode, repetition, recover_window_s=RECOVER_WINDOW_S):
    from mininet.link import TCLink
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch
    from mininet.topo import Topo

    class FourHostTopo(Topo):
        def build(self):
            switch = self.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
            for name, ip in H_IPS.items():
                self.addHost(name, ip=f"{ip}/24")
                self.addLink(name, switch)

    setLogLevel("warning")
    subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", str(CONTROLLER_APP)], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", str(REACTIVE_BASELINE_APP)], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)

    result = {
        "mode": mode, "repetition": repetition,
        "evidence_level": "measured_emulation_dry_run",
        "recover_window_s": recover_window_s,
        "valid_for_inference": True, "invalidation_reasons": [],
    }

    def invalidate(reason):
        result["valid_for_inference"] = False
        result["invalidation_reasons"].append(reason)

    net = None
    controller = None
    reader = None
    try:
        controller = launch_controller(mode)
        reader = BoundedLineReader(controller.stdout)
        net = Mininet(topo=FourHostTopo(), controller=None, switch=OVSSwitch,
                      link=TCLink, autoSetMacs=True)
        net.start()
        targets = [f"tcp:127.0.0.1:{OFP_PORT}"]
        if mode == "persistent":
            targets.append(f"tcp:127.0.0.1:{PERSISTENT_PORT}")
        subprocess.run(["ovs-vsctl", "set-controller", "s1", *targets], check=True)

        ready, err = read_until_ready(reader, time.monotonic() + READY_TIMEOUT_S)
        if ready is None or ready.get("event") != "ready":
            result["setup_failed"] = True
            result["setup_ready_error"] = err
            invalidate("controller_not_ready_at_setup")
            return result
        time.sleep(0.15)

        h1, h2, h3, h4 = net.get("h1", "h2", "h3", "h4")

        # Warm-up teaches h2<->h3. Setup installs+confirms the "old" h1<->h2
        # flow. Q2 uses h1<->h4 (untouched by either). Q3 uses h3<->h4
        # (also untouched by warm-up/setup/Q2) -- two distinct, verified-
        # unused pairs, not the same pair reused under different framing.
        h3.cmd(f"ping -c 2 -W 1 {H_IPS['h2']}")
        time.sleep(0.2)
        setup = cmd_ping(h1, H_IPS["h2"])
        result["setup_ping"] = {k: v for k, v in setup.items() if k != "raw"}
        result["setup_ping_raw"] = setup["raw"]
        flows_before = dump_flows()
        result["flows_before_stop_rc"] = flows_before["rc"]
        result["flows_before_stop_stdout"] = flows_before["stdout"]
        if not setup["valid"] or not setup["ok"]:
            result["setup_failed"] = True
            invalidate("setup_ping_failed_or_invalid")
            return result

        # Pre-flight: verify Q2's and Q3's pairs truly have no existing
        # rule (and record tool errors as such, not as "absent").
        pre_q2 = flow_status(flows_before, H_PORTS["h1"], H_MACS["h4"], H_PORTS["h4"])
        pre_q3 = flow_status(flows_before, H_PORTS["h3"], H_MACS["h4"], H_PORTS["h4"])
        result["q2_pair_preflight"] = pre_q2
        result["q3_pair_preflight"] = pre_q3
        if pre_q2["tool_error"] or pre_q3["tool_error"]:
            invalidate("dump_flows_tool_error_at_preflight")
        if pre_q2.get("exists"):
            invalidate("q2_pair_h1_h4_already_had_a_rule_before_downtime")
        if pre_q3.get("exists"):
            invalidate("q3_pair_h3_h4_already_had_a_rule_before_downtime")

        t_stop = time.monotonic()
        os.kill(controller.pid, signal.SIGTERM)
        controller.wait(timeout=5)
        result["t_stop_confirmed_s"] = time.monotonic() - t_stop

        # Q1: old flow (h1<->h2) during downtime.
        q1 = []
        for _ in range(5):
            r = cmd_ping(h1, H_IPS["h2"])
            q1.append({k: v for k, v in r.items() if k != "raw"})
            if not r["valid"]:
                invalidate("q1_unparseable_ping_output")
            time.sleep(0.3)
        result["q1_old_flow_during_downtime"] = q1
        result["q1_success_count"] = sum(1 for r in q1 if r["valid"] and r["ok"])

        # Q2: new flow (h1<->h4) during downtime.
        q2 = []
        for _ in range(5):
            r = cmd_ping(h1, H_IPS["h4"])
            q2.append({k: v for k, v in r.items() if k != "raw"})
            if not r["valid"]:
                invalidate("q2_unparseable_ping_output")
            time.sleep(0.3)
        result["q2_new_flow_during_downtime"] = q2
        result["q2_success_count"] = sum(1 for r in q2 if r["valid"] and r["ok"])

        # Re-verify absence of the Q3 target rule after Q2, before restart
        # -- confirms Q2's attempts did not somehow install anything.
        flows_after_q2 = dump_flows()
        result["flows_after_q2_rc"] = flows_after_q2["rc"]
        post_q2_pre_restart = flow_status(flows_after_q2, H_PORTS["h3"], H_MACS["h4"], H_PORTS["h4"])
        result["q3_pair_status_after_q2_before_restart"] = post_q2_pre_restart
        if post_q2_pre_restart["tool_error"]:
            invalidate("dump_flows_tool_error_after_q2")
        elif post_q2_pre_restart.get("exists"):
            invalidate("q3_pair_h3_h4_acquired_a_rule_during_downtime_before_restart")

        # Restart. The recovery monitor (Q3) starts immediately here, in a
        # background thread, concurrently with waiting for the "ready"
        # event on the main thread -- not sequenced after it.
        t_restart = time.monotonic()
        controller = launch_controller(mode)
        reader = BoundedLineReader(controller.stdout)
        result["t_restart_initiated_monotonic"] = t_restart

        q3_state = {"recovered": False, "t_recovered": None, "attempts": 0,
                     "poll_wait_s": 0.3, "history": []}
        recover_deadline = t_restart + recover_window_s

        def q3_monitor():
            while True:
                t_attempt_start = time.monotonic()
                if t_attempt_start >= recover_deadline:
                    break
                r = cmd_ping(h3, H_IPS["h4"], wait_s=q3_state["poll_wait_s"])
                q3_state["attempts"] += 1
                within_window = r["t_end"] <= recover_deadline
                q3_state["history"].append({
                    "t_start_offset_s": t_attempt_start - t_restart,
                    "t_end_offset_s": r["t_end"] - t_restart,
                    "within_window": within_window,
                    "valid": r["valid"], "ok": r["ok"], "parse_error": r["parse_error"],
                })
                # A success is only counted as "recovered within the
                # window" if the attempt that observed it also completed
                # within the window -- a success noticed after the
                # deadline is not backdated into it.
                if r["valid"] and r["ok"] and within_window:
                    q3_state["recovered"] = True
                    q3_state["t_recovered"] = r["t_end"]
                    break

        monitor_thread = threading.Thread(target=q3_monitor, daemon=True)
        monitor_thread.start()

        ready_events = []
        ready2, ready_err = read_until_ready(reader, t_restart + READY_TIMEOUT_S, ready_events)
        t_ready = time.monotonic()
        service_became_ready = ready2 is not None and ready2.get("event") == "ready"
        result["ready_after_restart"] = service_became_ready
        result["ready_wait_error"] = ready_err if not service_became_ready else None

        monitor_thread.join(timeout=recover_window_s + 5)
        if monitor_thread.is_alive():
            invalidate("q3_monitor_thread_did_not_finish")

        # Named precisely per review: this is when a connectivity probe
        # was FIRST observed to succeed ("connectivity-recovery observed
        # time"), not "the flow rule was confirmed" -- that is checked
        # next, as its own separately timestamped event.
        result["connectivity_recovery_observed"] = q3_state["recovered"]
        result["q3_attempts"] = q3_state["attempts"]
        result["q3_poll_wait_s"] = q3_state["poll_wait_s"]
        result["q3_history"] = q3_state["history"]
        if q3_state["recovered"]:
            result["connectivity_recovery_time_from_restart_s"] = q3_state["t_recovered"] - t_restart
            result["connectivity_recovery_time_from_ready_s"] = (
                q3_state["t_recovered"] - t_ready if service_became_ready else None
            )
        else:
            result["connectivity_recovery_time_from_restart_s"] = None
            result["connectivity_recovery_time_from_ready_s"] = None
            result["not_recovered_within_window"] = True
            if service_became_ready:
                result["service_not_recovered_despite_ready"] = True
            else:
                result["ready_not_observed_manual_intervention_not_attempted"] = True

        result["manual_intervention_required"] = None  # none was performed in this run

        # Rule confirmation is its OWN event, separately timestamped, not
        # folded into the ping-observed recovery moment above.
        t_rule_check = time.monotonic()
        flows_after = dump_flows()
        result["flows_after_recovery_rc"] = flows_after["rc"]
        rule_status = flow_status(flows_after, H_PORTS["h3"], H_MACS["h4"], H_PORTS["h4"])
        result["rule_confirmation_event"] = {
            "t_offset_from_restart_s": t_rule_check - t_restart,
            **rule_status,
        }
        if q3_state["recovered"]:
            if rule_status["tool_error"]:
                invalidate("dump_flows_tool_error_at_rule_confirmation")
            elif not rule_status.get("exists"):
                invalidate("connectivity_recovered_by_ping_but_no_matching_flow_rule_found")
            elif not rule_status.get("correct_action"):
                invalidate("connectivity_recovered_but_flow_rule_action_is_wrong")

    except Exception as exc:
        result["exception"] = repr(exc)
        invalidate("exception_during_trial")
    finally:
        if reader:
            reader.close()
        if net:
            net.stop()
        if controller and controller.poll() is None:
            controller.terminate()
            try:
                controller.wait(timeout=5)
            except Exception:
                controller.kill()
        subprocess.run(["mn", "-c"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result


def main():
    _self_test_parser()
    print("ping parser self-test: PASS")
    out_dir = ROOT / "results/network"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"r5_restart_recovery_limited_check_{stamp}.jsonl"
    # Limited check per the review: ONE trial per arm, separate from the
    # official 60-trial sample.
    modes = ["persistent", "reactive_osken"]
    with out_path.open("w") as f:
        for mode in modes:
            print(f"=== {mode} limited check ===", flush=True)
            r = run_trial(mode, 1)
            f.write(json.dumps(r) + "\n")
            f.flush()
            summary = {k: v for k, v in r.items()
                       if k not in ("q3_history", "flows_before_stop_stdout")}
            print(json.dumps(summary, indent=2))
    print(out_path)


if __name__ == "__main__":
    main()
