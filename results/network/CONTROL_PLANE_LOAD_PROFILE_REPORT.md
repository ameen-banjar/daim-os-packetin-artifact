# Sustained-Load Control-Plane Profile Report

Date: 20 July 2026
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

Neither existing Packet-In experiment reports throughput under sustained
arrivals, controller-process CPU/memory, or control-channel bytes:
`STAGE_PACKETIN_BRIDGE_REPORT.md` is a single functional trace,
`PACKETIN_LATENCY_BREAKDOWN_REPORT.md` decomposes one isolated reactive
event per trial (fresh topology each time), and `STAGE2_FULL_COMPARE_
REPORT.md` measures proactive rule installation, not the reactive path.
This experiment (task #18 of the TNSM revision plan) adds a sustained,
multi-sender reactive workload within a single controller lifetime, so
throughput, resource use, and control-traffic can be measured under load
rather than at a single instant.

## Design

One switch, 43 hosts: `h1` the shared destination, `h2` a primer, `h3`-
`h42` as 40 distinct senders, `h43` a dedicated signal host. Per trial (5
trials x {`process_per_rule`, `persistent`} = 10 real Mininet/OVS runs),
within one controller/topology lifetime (no teardown between sends, unlike
the latency-breakdown experiment, so this measures sustained load rather
than repeated cold starts):

1. `h2` pings `h1` once, untimed -- teaches DAIM Core `h1`'s (mac, port).
2. `h3`-`h42` each ping `h1` once, back-to-back -- 40 real reactive
   decisions, not a synthetic loop.
3. `h43` pings `h1` once, as an explicit end-of-window marker.

A fixed NO_RULE-event-count threshold was tried first and rejected during
development: each real ping's ARP request/reply and ICMP request/reply
each independently generate a NO_RULE event only if that specific
(in_port, dl_dst) direction has no flow installed yet, which depends on
prior traffic in a way that cannot be predicted from the sender count
alone (confirmed empirically: a 3-sender pilot produced 15-16 NO_RULE
events, not the naively expected 3). The dedicated signal host sidesteps
this: `daim_bridge_controller.py` (`DAIM_LOAD_PROFILE_SIGNAL_IP=h43`'s IP)
reports one `{"event": "load_profile", ...}` line as soon as it sees a
packet sourced from `h43`, i.e. only after every real sender has already
gone through, regardless of the exact event count that took.

Measured per trial:

- **Throughput**: `flows_installed / elapsed_s`, where `elapsed_s` runs
  from the controller's "ready" line (switch connected, table-miss rule
  installed) to the signal packet, so process/connection start-up is
  excluded.
- **CPU / memory**: `resource.getrusage(RUSAGE_SELF)` delta for the
  controller process, which also hosts DAIM Core in-process via ctypes
  (the same technique `stage2_full_compare.py` already uses for its own
  process-level accounting).
- **Control-traffic**: for `persistent`, the adapter's own real `send()`
  byte/message counters (`ovs_persistent_adapter.c`'s
  `daim_persistent_adapter_stats`); for `process_per_rule`, which has no
  persistent channel to instrument, `flows_installed` times the exact
  OpenFlow 1.3 Flow-Mod wire length computed by the same encoder
  (`daim_ovs_wire_flow_mod_size`, a new pure function added to the
  persistent adapter's module -- the wire format for a given match/action
  shape does not depend on which channel carries it). Each row records
  `control_bytes_source` (`measured` or `computed_wire_format`) so the two
  are never conflated.
- **ovs-vswitchd resource use**: sampled via `ps -o cputime=,rss=` before
  and after each trial. `ps`'s `cputime` field has whole-second
  resolution, too coarse to resolve a sub-second delta at this trial
  size; the mean deltas (0.4s for `process_per_rule`, 0.0s for
  `persistent`) are reported for completeness but are not a precise
  measurement at this scale.

## Result

n=5 trials per mode; bootstrap 95% CIs and the figure are in
`results/paper1/control_plane_load_profile_statistics.json` and
`control_plane_load_profile.png`. All 10 trials: 40/40 sender pings
succeeded, the priming ping succeeded, and the signal packet was observed.

| Metric | `process_per_rule` | `persistent` |
|---|---:|---:|
| Throughput (installs/s) | 74.4 [71.0, 77.3] | 272.3 [267.7, 275.9] |
| Controller CPU time (ms) | 89.8 [81.7, 97.9] | 37.1 [35.2, 39.0] |
| Controller max RSS (KiB) | 65654 | 65686 |
| Control bytes sent | 8064 (measured 8064 via persistent; identical `computed_wire_format` value) | 8064 |
| Control messages | 84 | 84 |
| Flows installed | 84 | 84 |
| NO_RULE events (mean) | 222.6 | 152.4 |

**`flows_installed` and `control_bytes_total` are identical between modes
in every trial (84 installs, 8064 bytes), which is an internal
cross-validation**: the two southbound paths process the same traffic
pattern and must reach the same number of resolved (non-flood) decisions
regardless of which adapter installs them, and `persistent`'s real
measured byte count (8064) exactly matches `process_per_rule`'s
`computed_wire_format` estimate (84 x 96 bytes) for the same 84 installs
-- corroborating that the wire-size computation used for
`process_per_rule`, which has no equivalent in-process byte counter, is
accurate rather than an unverified estimate.

**Persistent is 3.66x higher throughput and uses 2.42x less controller
CPU time under this sustained multi-sender workload.** This is a new
observation, not a restatement of the earlier findings: the single-event
latency breakdown (`PACKETIN_LATENCY_BREAKDOWN_REPORT.md`) showed a 4.5x
end-to-end speed-up for one isolated reactive event on a cold connection,
and the proactive benchmark (`STAGE2_FULL_COMPARE_REPORT.md`) showed a
narrowing 2.31x-1.26x advantage that pays a fresh connection cost per
switch. Here, one connection is established once and then amortised
across 40 real senders on the same switch -- the workload the persistent
adapter's design specifically targets, and the throughput/CPU gap is
correspondingly larger than either prior number, consistent with (not
contradicting) both.

**`no_rule_events` is lower for `persistent` (152.4) than `process_per_rule`
(222.6) despite installing the identical 84 flows.** This was not
predicted in the design and is not yet explained by this experiment; a
plausible mechanism is that `process_per_rule`'s per-rule subprocess
spawn adds enough latency for some flow installs to lose a race against
the next packet's arrival (causing an extra table-miss on the same
direction before the rule lands), which the persistent adapter's
single-`send()` path is fast enough to avoid more often -- but this
artifact does not instrument that race directly, so it is reported as an
observation, not a mechanism claim.

## Addendum: 21 July 2026 (30-repetition confirmation)

Task #19's paired re-run of the adapter-overhead microbenchmark found
that some of its 5-repetition point estimates did not survive properly
powered replication at the largest tested scale, so this experiment's
own n=5 (task #18's original design) was re-run at n=30 per mode (60
trials total, mode-major order -- not the blocked/randomised design task
#19 used, since this experiment has no size axis to confound with mode
order) to check whether the same caution applied here.

| Metric | `process_per_rule` (mean [95% CI], median [95% CI]) | `persistent` (mean [95% CI], median [95% CI]) |
|---|---|---|
| Throughput (installs/s) | 66.0 [62.1, 69.0], 68.3 [66.9, 69.6] | 253.0 [235.3, 268.5], 270.3 [259.2, 281.9] |
| Controller CPU time (ms) | 129.2 [102.1, 174.3], 106.6 [99.7, 110.5] | 50.8 [40.8, 63.2], 38.5 [35.3, 46.4] |
| Flows installed / control bytes | 84 / 8064 (every trial) | 84 / 8064 (every trial) |

**It replicates cleanly, with no ambiguity between the mean- and
median-based view**: persistent's throughput advantage is 3.8x (mean) or
4.0x (median), and its CPU-time advantage is 2.5x (mean) or 2.8x
(median) -- both consistent in direction and magnitude with the original
n=5 result (3.66x, 2.42x), and every confidence interval, mean- or
median-based, remains cleanly separated between modes. `flows_installed`
and `control_bytes_total` stayed at exactly 84 and 8064 in all 60
trials, reconfirming the cross-validation at 6x the sample size. Unlike
task #19's 64-switch finding, this experiment's fixed scale (one switch,
40 senders, no size axis) shows no comparable fragility: the original
5-repetition claim here was already sound, and the caution task #19
required for its own scaling axis does not generalise to every
experiment in this artifact indiscriminately -- each claim's robustness
was checked on its own terms, not assumed from another experiment's
result. Full data in `control_plane_load_profile_statistics.json`
(`median` and `median_ci` fields).

## Claim boundary

This measures one switch, one DAIM Core process, 40 senders converging on
a single already-known destination, within one controller lifetime. It is
not a multi-switch, multi-destination, or long-duration (beyond ~1.2s)
sustained-load result, and `ovs-vswitchd`'s own resource cost is reported
at whole-second `ps` resolution only, not a precise per-trial delta. The
control-byte accounting for `process_per_rule` is a wire-format
computation cross-validated against a matching measured count in this
run, not a live packet capture.
