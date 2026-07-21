# Packet-In Stage-Latency Breakdown Report

Date: 20 July 2026
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

External review of the manuscript (targeting IEEE TNSM) identified two
related gaps in the existing Packet-In experiment
(`STAGE_PACKETIN_BRIDGE_REPORT.md`): it is "a functional acceptance test
with one observed first-flow trace, not a latency distribution" (construct
validity), and the adapter-comparison experiments were "run sequentially
rather than randomised" with only five repetitions per condition (internal
validity). This experiment adds a repeated, per-stage-decomposed,
randomised-order measurement of the *reactive* Packet-In path -- distinct
from `stage2_full_compare.py`, which measures proactive rule installation
on switch connect, not a real Packet-In-triggered decision.

## Design

One OVS switch, three hosts (h1, h2, h3), OpenFlow 1.3, `failMode=secure`.
Each of 60 trials (30 repetitions x 2 adapter modes, single seeded shuffle,
seed 20260719) tears down and rebuilds the topology and controller process
from scratch, then:

1. **Untimed priming**: `h3` pings `h2` once, resolving ARP and teaching
   DAIM Core `h2`'s (MAC, port) without touching `h1`'s switch port.
2. **Timed trial**: `h1` pings `h2` once. The ICMP echo request is the
   first-ever packet on `h1`'s port (still a table miss), and `h2` is
   already known, so DAIM's `NO_RULE` handler deterministically learns
   `h1`, decides the destination port, writes the forwarding-table entry,
   and installs a real OVS flow. `daim_bridge_controller.py` matches this
   one event by parsed IPv4 destination (ARP traffic is forwarded normally
   but not timed) and reports nanosecond `CLOCK_MONOTONIC` timestamps at
   each stage boundary as one JSON line.

Two adapter modes are compared, both new instrumentation added to the
existing reactive bridge (`daim_bridge_controller.py` /
`daim_core_bridge.py` / `daim_learning_app.c`), not the proactive
benchmark:

- **`process_per_rule`**: the existing DAIM C adapter, spawning
  `ovs-ofctl` per rule (unchanged decision path).
- **`persistent`**: the from-scratch OpenFlow 1.3 client adapter
  (`ovs_persistent_adapter.c`, Section 4.3/6.3.1 of the manuscript), bound
  to the single switch via a background thread during controller startup,
  before the timed window begins. `persistent_flow_add` is fire-and-forget
  (a single `send()`, confirmed by reading the adapter source), so its
  cost should appear almost entirely in the switch-side confirmation stage
  rather than the install-call stage -- this is exactly what was measured.

Measured stage boundaries (nanosecond-comparable: same process, same
`CLOCK_MONOTONIC` source in Python via `time.perf_counter_ns()` and in C
via `clock_gettime`):

`dispatch` (Os-Ken handler entry -> pre-ctypes call, bridge-name cache
already warm) -> `ctypes_in` (crossing into C) -> `decision` (MAC
learn+lookup) -> `table_write` (`daim_table_write`) -> `install_call`
(`flow_add`) -> `ctypes_out` (crossing back to Python) -> `packetout_send`
(`OFPPacketOut`) -> `confirm` (polled `ovs-ofctl dump-flows` until the
installed `dl_dst=<mac>` rule is visible).

Out of scope, as a claim boundary: the interval between the switch's own
internal Packet-In generation and Os-Ken's socket read is not measured (no
switch/kernel-side instrumentation in this artifact); `dispatch` starts at
Os-Ken's handler entry, matching how the existing `direct_osken` baseline
starts timing at FlowMod send rather than at TCP connect.

## Result

Mean stage latency (us) and total, n=30 per mode, bootstrap 95% CI in
`packetin_latency_breakdown_statistics.json`; figure in
`packetin_latency_breakdown.png`.

| Stage | process_per_rule | persistent |
|---|---:|---:|
| Os-Ken dispatch + bridge lookup | 0.090 ms | 0.087 ms |
| ctypes crossing (in) | 0.018 ms | 0.014 ms |
| Core decision (learn+lookup) | 0.001 ms | 0.001 ms |
| daim_table_write | 0.005 ms | 0.000 ms |
| OVS install call (flow_add) | 9.813 ms | 0.024 ms |
| ctypes crossing (out) | 0.005 ms | 0.002 ms |
| PacketOut send | 0.039 ms | 0.023 ms |
| Switch-side confirmation (dump-flows poll) | 1.789 ms | 2.437 ms |
| **Total** | **11.760 ms** | **2.588 ms** |

All 60 trials passed their priming ping, timed ping, install, and
confirmation checks (60/60 on each).

**DAIM Core's own logic is fast and identical in shape across modes**:
dispatch, ctypes crossing, decision, and table-write together cost well
under 0.15 ms in both modes and are not where adapter choice matters.

**The install-call stage collapses from 9.813 ms to 0.024 ms**
(410x) under the persistent adapter, exactly as its fire-and-forget
`send()` design predicts, confirming the same architectural mechanism
already reported for the proactive benchmark (Section 6.3.1), now isolated
on the reactive path.

**The switch-side confirmation stage is the opposite direction**: 2.437 ms
for `persistent` versus 1.789 ms for `process_per_rule` (1.36x slower).
`ovs-ofctl add-flow` applies its Flow-Mod synchronously over OVS's
management control socket before the subprocess exits, so the first
`dump-flows` poll iteration typically already observes the installed rule.
A Flow-Mod delivered asynchronously over the persistent adapter's separate
auxiliary-controller connection takes measurably longer to become visible
through that same management path, so the polling loop more often needs a
second iteration. This cost was invisible in the proactive benchmark's
single install/confirm timer; decomposing the reactive path is what
surfaces it.

**Net effect**: because the persistent adapter's connection is already
established before the timed window starts (unlike the proactive
benchmark, where every switch pays a fresh-connection cost inside the
timed interval), the reactive path is 4.544x faster end-to-end under the
persistent adapter (2.588 ms vs. 11.760 ms) despite the confirmation-stage
regression -- the install-call saving dominates.

## Claim boundary

This measures one reactive NO_RULE Packet-In event per trial on a single
switch, not flow-setup latency under concurrent load, controller
throughput, or a distribution over varying table sizes (DAIM Core's
forwarding-table lookup is a linear scan; its scaling with table size is
not characterised here). It is not a repeated-install-on-an-already-
connected-switch workload for the proactive path (that remains the
follow-up experiment named in `STAGE2_FULL_COMPARE_REPORT.md`). The
`confirm` stage cost is specific to polling `ovs-ofctl dump-flows`; it is
not a wire-level OpenFlow acknowledgement, and no barrier/echo-based
confirmation exists yet for the persistent adapter.
