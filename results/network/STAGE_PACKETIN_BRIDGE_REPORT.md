# Packet-In to DAIM Core NO_RULE Bridge Report

Date: 18 July 2026
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

`implementation/TEST_REPORT.md`'s "Next implementation increment" listed two
gaps: a Packet-In event receiver with Core callback emission, and translation
from `packet_forwarding_table_entry` to OpenFlow matches/actions. Both are now
implemented and exercised against a real OpenFlow 1.3 controller and OVS.

## Design

- `implementation/src/daim_learning_app.c` is a small DAIM application: it
  registers a handler for the `NO_RULE` signal via `daim_signal`, performs
  per-bridge MAC learning, writes a `packet_forwarding_table_entry` to
  `DAIM_PACKET_FORWARDING_TABLE` via `daim_table_write`, and — when the
  destination is known — calls the bound switch adapter's `flow_add` to
  install a real OVS rule.
- `implementation/Makefile` gains a `libdaim_core.so` target (PIC objects of
  `daim_core.c`, `ovs_switch_adapter.c`, `daim_learning_app.c`) so this logic
  is callable from a non-C process in the same host.
- `network/daim_core_bridge.py` is a ctypes binding to that shared library. It
  mirrors `struct no_rule_packet_info` byte-for-byte (`_pack_ = 1`, verified
  `sizeof == 35` to match the recorded ABI probe) and wraps the OVS executor
  callback so DAIM's `flow_add` runs real `ovs-ofctl` commands.
- `network/daim_bridge_controller.py` is a real Os-Ken OpenFlow 1.3
  controller. On every Packet-In it resolves the OVS bridge name for the
  datapath id, then calls `DaimCoreBridge.packet_in(...)`, which drives
  `daim_core_emit(NO_RULE, ...)` in C. The controller only performs what DAIM
  Core does not implement yet (`port_write` is unsupported in the OVS
  adapter): sending the buffered first packet back out via `OFPPacketOut`. It
  never issues its own `OFPFlowMod` — persistent rule installation is entirely
  DAIM Core's decision, executed through the OVS adapter.

## Test

`network/run_daim_bridge_smoke.py` runs the same two-switch/two-host Mininet
topology as `run_real_controller_smoke.py`, but with
`daim_bridge_controller.py` as the controller.

## Result

- Both switches connected to the controller before traffic (`tcp:127.0.0.1:6653`).
- Before the first ping, only the priority-0 table-miss rule was present on
  each switch.
- After a 5-packet ping, `ovs-ofctl dump-flows` showed four new
  `priority=100,in_port=<p>,dl_dst=<mac> actions=output:<p>` rules (two per
  switch) — the exact format produced by `daim_learning_app.c`'s
  `install_flow`, not a controller-issued FlowMod. `daim_installed_dl_dst_rules=4`.
- A second 5-packet ping passed with 0% loss using the installed rules.
- The controller process was then killed; a further 10-packet ping still
  passed with 0% loss because the DAIM-installed OVS rules persist
  independently of the controller connection.
- Raw evidence, including full flow dumps at each stage: `daim_bridge_smoke.json`.

## Claim boundary

This demonstrates that a real OpenFlow Packet-In reaches `daim_core_emit(NO_RULE, ...)`
and that the resulting decision becomes a real OVS flow — the concrete gap
this increment targeted. It does not yet demonstrate:

- L3/L4 matching (`packet_forwarding_table_entry`'s IP/port/VLAN fields are
  zeroed; only `in_port` and `mac_dst` are matched, mirroring the L2 learning
  switch this replaces);
- a DAIM Core that itself terminates an OpenFlow session (Python/Os-Ken still
  owns the wire protocol and buffered-packet delivery);
- multiple concurrent DAIM applications, authentication, or lifecycle
  management;
- any autonomic/self-healing behaviour — that is Task 6/7's scope (an
  event-driven DAIM Agent reacting to link state, not Packet-In).
