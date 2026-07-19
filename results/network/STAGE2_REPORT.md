# Stage 2 Flow-Installation Benchmark Report

Date: 18 July 2026  
Evidence level: `measured_emulation`

## Design

The benchmark used a real Ubuntu/Mininet/Open vSwitch environment and a linear
topology with one host per switch. For each switch, the compiled DAIM OVS
adapter installed one OpenFlow 1.3 rule (`priority=100,ip,actions=normal`).
Five independent topology repetitions were run at each size: 8, 16, 32, and
64 switches. Every repetition included a three-packet ping from the first to
the last host and retained the raw row even if the ping failed.

## Results

The raw observations are in `stage2_raw.csv`; derived values are in
`stage2_summary.csv`. All 20 repetitions passed the ping check (5/5 at each
size). The summary includes p50, p95, and p99 of the five repetition-level
mean installation times, total installation time, harness CPU time, and
maximum resident memory.

The p95 and p99 values are descriptive only because each size has five
repetitions. They are not confidence bounds and should not be used as a final
performance claim.

## Measurement boundary

The timing surrounds the DAIM C adapter process invoking `ovs-ofctl` for one
rule per switch. It is not yet a new-flow arrival benchmark, does not measure
OVS daemon CPU directly, and has no controller baseline. It therefore supports
the claim that the current adapter completed the specified installation task
at these sizes, not a claim of superiority or production scalability.

## Next strengthening step

Add a fixed central-controller baseline, measure OVS and controller CPU/RAM
from inside Linux, use controlled new-flow traces, increase repetitions, and
separate process-start overhead from the actual OpenFlow transaction.

