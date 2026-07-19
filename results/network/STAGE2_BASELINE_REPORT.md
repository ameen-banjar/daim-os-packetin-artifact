# Stage 2 matched baseline report

Date: 18 July 2026  
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0  
Evidence: `measured_emulation`

The same linear topologies (8, 16, 32, and 64 switches), one rule per switch,
five repetitions, and end-to-end ping check were executed through two software
paths: the DAIM C OVS adapter and direct `ovs-ofctl`. All 40 runs per mode
passed the connectivity check. Raw data are in `stage2_baseline_raw.csv`; the
derived values are in `stage2_baseline_summary.csv`.

The direct path was faster in this harness (mean per-switch setup: 9.67--12.64
ms) than the DAIM adapter (12.82--16.21 ms). This is an adapter/process-overhead
baseline, not a comparison of forwarding performance or a claim of superiority.
The next fair baseline should use a persistent controller connection and report
CPU, memory, OpenFlow messages, and confidence intervals.
