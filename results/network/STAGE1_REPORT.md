# Stage 1 DAIM Core + Open vSwitch Integration Report

Date: 18 July 2026  
Evidence level: `measured_emulation`

## Environment

- Ubuntu 24.04 LTS, ARM64, Linux 6.8.0-41-generic.
- Lima/QEMU VM: 4 vCPU, 6 GiB RAM, 30 GiB disk.
- Open vSwitch 3.3.4.
- Mininet 2.3.0.
- iperf3 3.16.
- Clang 18.1.3 and GCC 13.3.0.

## Test

The Linux build compiled and passed the Core, adapter, and concurrency tests.
Mininet then created two OVS switches (`s1`, `s2`) and two hosts (`h1`, `h2`)
without a controller. The compiled C DAIM OVS adapter installed four explicit
OpenFlow 1.3 rules, providing bidirectional forwarding across the two switches.

## Result

- Four flow-install commands returned success.
- `ovs-ofctl -O OpenFlow13 dump-flows` confirmed all four rules.
- Flow counters increased during the connectivity test.
- Five ICMP packets were transmitted and five received.
- Packet loss: 0%.
- Reported ping RTT min/avg/max/mdev: 0.045/0.266/0.984/0.363 ms.
- Automated stage verification: PASS.

The raw JSON is `two_switch_demo.json`. It includes the flow strings, OVS flow
dumps, ping output, and per-command host-clock instrumentation.

## Failed attempt retained

Attempt 001 failed because the first adapter invocation did not force OpenFlow
1.3. The OVS adapter and unit test were corrected to include
`-O OpenFlow13`. See `attempt_001_failure.md`.

## Claim boundary

This demonstrates a real two-switch OVS integration smoke test. It does not
establish scalable performance, comparative superiority, controller behaviour,
self-healing, or hardware validity. The four per-command timing values are not
a benchmark because no warm-up, repetition protocol, load control, or baseline
was applied.

