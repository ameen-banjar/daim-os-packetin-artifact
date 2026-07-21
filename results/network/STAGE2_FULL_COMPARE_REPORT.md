# Stage 2 Four-Way Comparison Report

Date: 19 July 2026
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

External review of the manuscript (targeting IEEE TNSM) identified that the
original two-way comparison (DAIM adapter vs. direct `ovs-ofctl`) confounded
process-spawn cost, DAIM Core/ctypes cost, and OpenFlow installation cost,
and that the DAIM adapter's process-per-rule design was a predictable,
uninteresting result rather than evidence about DAIM's architecture. This
experiment adds two new measured paths so the four costs are isolated:

1. `daim_process_per_rule` -- the original DAIM C adapter (unchanged): spawns
   `ovs-ofctl` as a subprocess for every rule.
2. `daim_persistent` -- **new**: the DAIM C adapter using a from-scratch
   OpenFlow 1.3 client (`ovs_persistent_adapter.c`) that opens one persistent
   TCP connection per switch (registered as an auxiliary OpenFlow controller
   alongside the primary) and sends a raw `OFPT_FLOW_MOD`, with no
   subprocess per rule.
3. `direct_ovs_cli` -- the original baseline (unchanged): `ovs-ofctl`
   invoked directly, no DAIM.
4. `direct_osken` -- **new**: a plain Os-Ken controller with no DAIM
   involvement, installing the same rule proactively on switch connect and
   confirming completion via `OFPT_BARRIER_REQUEST`/`REPLY` (the standard
   way to know a switch has finished processing a Flow-Mod).

All four paths install the identical rule (`priority=100,ip,actions=normal`)
on the identical linear topology and sizes (8/16/32/64 switches) used by the
original Stage 2 benchmark, with 5 repetitions per (mode, size).

## Result

| Switches | daim_process_per_rule | daim_persistent | direct_ovs_cli | direct_osken |
|---:|---:|---:|---:|---:|
| 8  | 13.557 ms | 5.861 ms | 9.890 ms | 1.630 ms |
| 16 | 13.181 ms | 6.492 ms | 9.872 ms | 2.775 ms |
| 32 | 13.853 ms | 8.799 ms | 10.402 ms | 5.282 ms |
| 64 | 16.903 ms | 13.377 ms | 12.959 ms | 11.298 ms |

(Mean per-switch install/confirm time; bootstrap 95% CIs and the figure are
in `results/paper1/stage2_full_compare_statistics.json` and
`stage2_full_compare.png`.) All 80 runs passed their connectivity check.

**The persistent adapter is a real improvement over the process-per-rule
adapter, but the improvement is not constant.** It is fastest relative to
the original design at small scale (2.31x faster at 8 switches: 5.861 ms vs.
13.557 ms) and slowest at large scale (1.26x faster at 64 switches: 13.377
ms vs. 16.903 ms). This is expected in this specific workload: each switch
in this benchmark needs a freshly established connection (one rule per
switch, no repeated installs on an already-connected switch), so the
persistent adapter cannot amortise its connection-setup cost here the way it
would under a sustained, repeated-install workload -- and general
system/OVS load at larger switch counts affects every mode, narrowing
relative gaps.

**The gap between DAIM (persistent) and a bare native controller connection
also narrows with scale**, from 3.60x slower than `direct_osken` at 8
switches to 1.18x slower at 64 switches. Read together with the table above,
this indicates that as switch count grows, connection-independent system
load increasingly dominates all four paths' timings, while DAIM's own
architectural overhead (ctypes call, Core table write, learning-application
dispatch) becomes proportionally smaller.

## Claim boundary

This measures the same thing the original Stage 2 benchmark measured --
process-mediated rule-installation time for one proactive rule per switch --
extended to isolate four different southbound paths. It is not a flow-setup
latency distribution, controller throughput measurement, or evidence about
DAIM's distributed-deployment properties (a single DAIM Core process serves
all switches by bridge name in this artifact; see the manuscript's threats
to validity). A workload with repeated installs on an already-connected
switch, which would better showcase the persistent adapter's intended
advantage, is a distinct planned experiment.
