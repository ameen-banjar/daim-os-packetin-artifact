# Additional controller service results

The fixed schedule contains 340 attempts; 340 were recorded. This report describes application/configuration behaviour in one emulated host environment. It does not rank controller architectures or estimate maximum sustainable throughput.

The original collector was amended after attempt eight, which failed during setup. That record remains an instrumentation error and was not replaced. The first resume failed a metadata check before starting any new trial. The amendments, original and updated sources, and every attempted schedule slot are retained.

## Attempt accounting

| Platform | Scheduled | Recorded | Completed workload | Health-ready completed runs | Setup or execution error | Connection timeout | Not listening |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DAIM process-per-rule | 85 | 85 | 85 | 85 | 0 | 0 | 0 |
| Reactive Os-Ken | 85 | 85 | 84 | 84 | 1 | 0 | 0 |
| ONOS native fwd | 85 | 85 | 85 | 85 | 0 | 0 | 0 |
| OpenDaylight native L2Switch | 85 | 85 | 85 | 54 | 0 | 0 | 0 |

Completion is an instrumentation status, not a statement that packets were delivered or service recovered. Health readiness is the separate bounded health-pair check; its failure does not remove a completed workload.

## Concurrent new endpoint pairs

Each cell is the number of runs in which all target probes succeeded divided by completed runs. Five runs were scheduled per cell. Health-readiness failures remain in this denominator when the measured batch ran. Raw successful/valid probe totals and nominal exact intervals are in the statistics JSON.

| Switches | New pairs | DAIM | Os-Ken | ONOS | OpenDaylight |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 5/5 | 5/5 | 5/5 | 3/5 |
| 1 | 8 | 5/5 | 5/5 | 5/5 | 3/5 |
| 1 | 32 | 5/5 | 4/4 | 5/5 | 4/5 |
| 4 | 1 | 5/5 | 5/5 | 5/5 | 4/5 |
| 4 | 8 | 5/5 | 5/5 | 5/5 | 3/5 |
| 4 | 32 | 5/5 | 5/5 | 5/5 | 2/5 |
| 8 | 1 | 5/5 | 5/5 | 5/5 | 3/5 |
| 8 | 8 | 5/5 | 5/5 | 5/5 | 4/5 |
| 8 | 32 | 5/5 | 5/5 | 5/5 | 3/5 |
| 16 | 1 | 5/5 | 5/5 | 5/5 | 4/5 |
| 16 | 8 | 5/5 | 5/5 | 5/5 | 4/5 |
| 16 | 32 | 5/5 | 5/5 | 5/5 | 2/5 |

The workload includes ARP and native forwarding-policy behaviour. When pairs are fewer than switches, some switches carry only health-check traffic. The topology consists of separate L2 domains sharing a controller.

## Service observed after disruption and restoration actions

Post-action observation is eligible only after a successful pre-fault baseline, verified injection where required, and an actual observation attempt. A successful response must finish within the 30-second window. Conditional times omit non-successes; counts remain visible. Restart is externally initiated, not automatic failover. These frozen-analysis counts alone do not establish recovery from an observed outage: a native application may continue serving the new destination while its controller is stopped. The supplementary outage interpretation separates those cases using the retained downtime probes. Host movement has no probe during the detach/attach gap.

| Platform | Event | Recorded | Eligible | Service observed within 30 s | No service observed within 30 s | Ineligible completed | Median post-action observation in s among successes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DAIM process-per-rule | link_restore | 5 | 5 | 5 | 0 | 0 | 0.042 |
| DAIM process-per-rule | switch_restart | 5 | 5 | 5 | 0 | 0 | 1.256 |
| DAIM process-per-rule | host_move | 5 | 5 | 0 | 5 | 0 | — |
| DAIM process-per-rule | controller_restart | 5 | 5 | 5 | 0 | 0 | 2.435 |
| DAIM process-per-rule | controller_crash | 5 | 5 | 5 | 0 | 0 | 2.338 |
| Reactive Os-Ken | link_restore | 5 | 5 | 5 | 0 | 0 | 0.045 |
| Reactive Os-Ken | switch_restart | 5 | 5 | 5 | 0 | 0 | 1.326 |
| Reactive Os-Ken | host_move | 5 | 5 | 0 | 5 | 0 | — |
| Reactive Os-Ken | controller_restart | 5 | 5 | 5 | 0 | 0 | 2.384 |
| Reactive Os-Ken | controller_crash | 5 | 5 | 5 | 0 | 0 | 2.403 |
| ONOS native fwd | link_restore | 5 | 5 | 5 | 0 | 0 | 0.060 |
| ONOS native fwd | switch_restart | 5 | 5 | 5 | 0 | 0 | 1.253 |
| ONOS native fwd | host_move | 5 | 5 | 0 | 5 | 0 | — |
| ONOS native fwd | controller_restart | 5 | 5 | 2 | 3 | 0 | 28.819 |
| ONOS native fwd | controller_crash | 5 | 5 | 0 | 5 | 0 | — |
| OpenDaylight native L2Switch | link_restore | 5 | 1 | 1 | 0 | 4 | 0.015 |
| OpenDaylight native L2Switch | switch_restart | 5 | 4 | 4 | 0 | 1 | 26.380 |
| OpenDaylight native L2Switch | host_move | 5 | 5 | 0 | 5 | 0 | — |
| OpenDaylight native L2Switch | controller_restart | 5 | 3 | 3 | 0 | 2 | 0.024 |
| OpenDaylight native L2Switch | controller_crash | 5 | 3 | 3 | 0 | 2 | 0.014 |

## Controller service during downtime

This supplementary interpretation was specified during collection after a completed ODL case showed successful communication to the new destination while its controller service was stopped. It changes neither the raw data nor the frozen post-action success counts. Recovery after observed loss is a narrower subset; successful downtime probes represent reachability at those probe times, not proof of continuous service.

| Platform | Event | Eligible | Existing destination works during stop | New destination works during stop | New-destination probe loss observed | Service restored within 30 s after observed loss |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DAIM process-per-rule | controller_crash | 5 | 5 | 0 | 5 | 5 |
| DAIM process-per-rule | controller_restart | 5 | 5 | 0 | 5 | 5 |
| OpenDaylight native L2Switch | controller_crash | 3 | 3 | 3 | 0 | 0 |
| OpenDaylight native L2Switch | controller_restart | 3 | 3 | 3 | 0 | 0 |
| ONOS native fwd | controller_crash | 5 | 5 | 0 | 5 | 0 |
| ONOS native fwd | controller_restart | 5 | 0 | 0 | 5 | 2 |
| Reactive Os-Ken | controller_crash | 5 | 5 | 0 | 5 | 5 |
| Reactive Os-Ken | controller_restart | 5 | 5 | 0 | 5 | 5 |

## Batch duration and controller resources

Medians below are across completed runs, including runs with packet loss. Batch duration is wall time for all concurrent probe tasks, not an average per-flow installation time. CPU includes controller subprocess children but excludes OVS and the probe harness; current memory is an after-batch snapshot, not a per-trial peak. Measurements from short batches should not be interpreted as stable utilization rates. Read resource use alongside delivered-service counts: low CPU use in a failed batch is not evidence of greater efficiency, and native application/runtime footprints differ.

| Platform | Switches | Pairs | Runs | Median batch in ms | CPU observations | Median CPU seconds | Memory observations | Median current memory in MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DAIM process-per-rule | 1 | 1 | 5 | 44.922 | 5 | 0.021165 | 5 | 48.04 |
| DAIM process-per-rule | 1 | 8 | 5 | 182.166 | 5 | 0.100869 | 5 | 48.01 |
| DAIM process-per-rule | 1 | 32 | 5 | 616.095 | 5 | 0.359895 | 5 | 47.98 |
| DAIM process-per-rule | 4 | 1 | 5 | 36.242 | 5 | 0.017738 | 5 | 48.07 |
| DAIM process-per-rule | 4 | 8 | 5 | 171.018 | 5 | 0.094747 | 5 | 48.06 |
| DAIM process-per-rule | 4 | 32 | 5 | 627.387 | 5 | 0.379711 | 5 | 48.04 |
| DAIM process-per-rule | 8 | 1 | 5 | 30.723 | 5 | 0.015526 | 5 | 48.09 |
| DAIM process-per-rule | 8 | 8 | 5 | 161.683 | 5 | 0.089595 | 5 | 48.13 |
| DAIM process-per-rule | 8 | 32 | 5 | 598.103 | 5 | 0.354315 | 5 | 48.03 |
| DAIM process-per-rule | 16 | 1 | 5 | 24.436 | 5 | 0.012190 | 5 | 48.21 |
| DAIM process-per-rule | 16 | 8 | 5 | 155.923 | 5 | 0.086945 | 5 | 48.20 |
| DAIM process-per-rule | 16 | 32 | 5 | 606.130 | 5 | 0.350633 | 5 | 48.10 |
| Reactive Os-Ken | 1 | 1 | 5 | 8.962 | 5 | 0.001869 | 5 | 47.88 |
| Reactive Os-Ken | 1 | 8 | 5 | 20.114 | 5 | 0.007981 | 5 | 47.88 |
| Reactive Os-Ken | 1 | 32 | 4 | 48.679 | 4 | 0.019353 | 4 | 47.88 |
| Reactive Os-Ken | 4 | 1 | 5 | 8.130 | 5 | 0.001887 | 5 | 47.88 |
| Reactive Os-Ken | 4 | 8 | 5 | 15.678 | 5 | 0.007363 | 5 | 47.87 |
| Reactive Os-Ken | 4 | 32 | 5 | 41.450 | 5 | 0.020129 | 5 | 47.92 |
| Reactive Os-Ken | 8 | 1 | 5 | 5.976 | 5 | 0.001306 | 5 | 47.94 |
| Reactive Os-Ken | 8 | 8 | 5 | 11.465 | 5 | 0.004817 | 5 | 47.95 |
| Reactive Os-Ken | 8 | 32 | 5 | 31.888 | 5 | 0.016253 | 5 | 47.94 |
| Reactive Os-Ken | 16 | 1 | 5 | 4.908 | 5 | 0.001139 | 5 | 48.03 |
| Reactive Os-Ken | 16 | 8 | 5 | 11.122 | 5 | 0.004288 | 5 | 48.02 |
| Reactive Os-Ken | 16 | 32 | 5 | 29.186 | 5 | 0.014321 | 5 | 48.01 |
| ONOS native fwd | 1 | 1 | 5 | 12.757 | 5 | 0.016947 | 5 | 1044.73 |
| ONOS native fwd | 1 | 8 | 5 | 33.197 | 5 | 0.065684 | 5 | 1001.83 |
| ONOS native fwd | 1 | 32 | 5 | 110.000 | 5 | 0.216403 | 5 | 1053.43 |
| ONOS native fwd | 4 | 1 | 5 | 8.488 | 5 | 0.018320 | 5 | 1050.34 |
| ONOS native fwd | 4 | 8 | 5 | 29.189 | 5 | 0.070108 | 5 | 1011.52 |
| ONOS native fwd | 4 | 32 | 5 | 57.008 | 5 | 0.100365 | 5 | 1053.32 |
| ONOS native fwd | 8 | 1 | 5 | 8.672 | 5 | 0.011208 | 5 | 1046.95 |
| ONOS native fwd | 8 | 8 | 5 | 14.217 | 5 | 0.037007 | 5 | 1053.98 |
| ONOS native fwd | 8 | 32 | 5 | 44.122 | 5 | 0.076431 | 5 | 1046.59 |
| ONOS native fwd | 16 | 1 | 5 | 7.058 | 5 | 0.011698 | 5 | 1045.56 |
| ONOS native fwd | 16 | 8 | 5 | 10.618 | 5 | 0.020358 | 5 | 1048.21 |
| ONOS native fwd | 16 | 32 | 5 | 38.620 | 5 | 0.067446 | 5 | 1027.79 |
| OpenDaylight native L2Switch | 1 | 1 | 5 | 7.077 | 5 | 0.025176 | 5 | 784.17 |
| OpenDaylight native L2Switch | 1 | 8 | 5 | 38.448 | 5 | 0.088531 | 5 | 766.80 |
| OpenDaylight native L2Switch | 1 | 32 | 5 | 58.273 | 5 | 0.148466 | 5 | 771.23 |
| OpenDaylight native L2Switch | 4 | 1 | 5 | 4.308 | 5 | 0.019203 | 5 | 752.70 |
| OpenDaylight native L2Switch | 4 | 8 | 5 | 17.616 | 5 | 0.072413 | 5 | 738.49 |
| OpenDaylight native L2Switch | 4 | 32 | 5 | 1040.964 | 5 | 0.200238 | 5 | 753.21 |
| OpenDaylight native L2Switch | 8 | 1 | 5 | 3.771 | 5 | 0.020421 | 5 | 749.65 |
| OpenDaylight native L2Switch | 8 | 8 | 5 | 12.918 | 5 | 0.045601 | 5 | 728.20 |
| OpenDaylight native L2Switch | 8 | 32 | 5 | 56.825 | 5 | 0.151450 | 5 | 749.01 |
| OpenDaylight native L2Switch | 16 | 1 | 5 | 2.949 | 5 | 0.013969 | 5 | 743.67 |
| OpenDaylight native L2Switch | 16 | 8 | 5 | 13.443 | 5 | 0.042148 | 5 | 725.74 |
| OpenDaylight native L2Switch | 16 | 32 | 5 | 1031.916 | 5 | 0.318301 | 5 | 771.26 |

## Physical-host resource context

The host monitor retained 787 samples with 0 command/parse errors. Interval CPU idle ranged from 19.90% to 88.20% (median 75.29%). Memory-pressure code counts were `{'2': 787}`. Swap counters increased by 254,480 input pages and 233,098 output pages; the recorded page sizes were [16384] bytes.

Memory pressure and host swapping were therefore present during the overall monitoring window, which also includes pauses and diagnostics. These host-wide counters cannot allocate swapping to a particular controller or prove the cause of a failed or slow trial. The timing and service observations describe this constrained environment; they do not establish isolated controller costs or production reliability. No completed attempt was discarded based on these later summaries.

## Interpretation limits

There are five scheduled runs per platform/condition, shared controller sessions within blocks, native application differences, and a documented collector amendment. Nominal exact intervals do not remove these limitations or establish independence; no multiplicity-adjusted platform ranking is attempted. Failures describe the tested configuration. A causal explanation requires a separately controlled investigation.

This campaign does not establish distributed state consistency, automatic standby failover, behaviour on physical switches, or production-scale performance. Three unrelated pre-existing OVS bridges remained in the VM; host monitoring provides context rather than proof of an isolated host.

## Provenance

Statistics source: `statistics.json`. SHA-256: `c996a6747e8ee90568e5f664b5a63f5a22c1e53cd62c9717e1affbac58ac4061`.

Supplementary outage interpretation: `outage_interpretation.json`. SHA-256: `84d2f190dd11c76ad610a47b7e7ebf2f1a403f63e931b93ccdc1507e02bb71d7`.

Host context: `host_resource_summary.json`. SHA-256: `423f103277283dd39c997f2369b57e0b53fc4ad8f685299a41b71457652294b1`.

The statistics JSON contains hashes of every raw attempt file. The frozen plan, source snapshots, amendments, per-session application logs, flow dumps, identities and raw ping outputs remain in the corresponding data directory.
