# Matched Reactive Packet-In Latency Report

Date: 9 August 2026
Environment: Ubuntu 24.04 ARM64, OVS 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence: `measured_emulation`

## Design

The experiment compares three reactive paths under one completion definition:
Os-Ken Packet-In handler entry until the exact priority-100 rule is observable
with `ovs-ofctl dump-flows`. A single-switch, three-host topology is rebuilt for
every trial. An untimed ping teaches the destination; a timed first packet from
a previously unused port triggers one known-destination decision.

- `process_per_rule`: Os-Ken -> ctypes -> DAIM Core -> C application ->
  subprocess OVS adapter.
- `persistent`: the same DAIM path with a pre-established OpenFlow 1.3 adapter.
- `reactive_osken`: DAIM-free Os-Ken L2 learning baseline with the same
  Packet-In stimulus, `(in_port, eth_dst)` match, priority, action, PacketOut,
  and external rule-observation boundary.

Thirty repetitions per mode were drawn from one seeded shuffle (90 trials;
seed 20260719). All trials passed priming, ping, installation, and confirmation.
The raw CSV records monotonic timestamps and success fields. The analysis uses
20,000 bootstrap resamples and reports stage and total mean, SD, median, p95,
p99, maximum, and a 95% bootstrap interval for the mean.

## Results

| Mode | Mean [95% CI] | Median | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|
| DAIM process-per-rule | 14.396 [13.168, 15.784] ms | 12.631 ms | 20.837 ms | 23.873 ms | 24.767 ms |
| DAIM persistent | 2.661 [2.196, 3.415] ms | 2.298 ms | 3.410 ms | 9.582 ms | 12.050 ms |
| Reactive Os-Ken | 2.934 [2.514, 3.399] ms | 2.373 ms | 5.437 ms | 5.882 ms | 5.923 ms |

Persistent DAIM is 9.3% lower in mean than the matched Os-Ken baseline, but the
confidence intervals overlap; the defensible result is practical comparability,
not superiority. Their medians differ by only 0.075 ms. Persistent DAIM has the
lower p95 but the higher p99 and maximum: rare switch-observation delays dominate
its upper tail. Process-per-rule DAIM is approximately 5.4x slower than
persistent DAIM, with subprocess installation dominating.

## Claim boundary

This is a single-switch, isolated-event, software-emulation experiment. It does
not measure switch-to-controller transport before handler entry, concurrent
throughput, hardware forwarding, or production scalability. The polling-based
completion boundary is deliberately identical across modes but includes polling
granularity. Machine-readable statistics are in
`results/paper1/packetin_latency_breakdown_statistics.json`.
