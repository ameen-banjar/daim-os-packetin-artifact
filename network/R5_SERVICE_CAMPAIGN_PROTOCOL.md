# Additional controller service experiments

This record explains the executable plan for the additional reviewer experiments. The source and schedule were frozen before collection in `experiments/results/network/r5_service_campaign_20261001/frozen_plan.json`; this readable explanation was written during collection. It is not an additional preregistration and does not supersede the frozen sources or the explicit amendments.

## Questions and coverage

The campaign asks how four deployed learning applications behave under increasing switch counts and concurrent new endpoint pairs, and after five specified disruptions. It measures externally observed service and controller process-group resources. The applications use their native forwarding policies, so this is an application/configuration comparison, not an isolation of controller architecture or a matched internal Packet-In benchmark.

| Dimension | Scheduled cases |
| --- | --- |
| Platforms | DAIM process-per-rule, reactive Os-Ken, ONOS 2.7.0 native fwd, OpenDaylight 0.24.0 native L2Switch |
| Switch count | 1, 4, 8, 16 independent L2 domains under one controller |
| Concurrent new endpoint pairs | 1, 8, 32 total pairs, allocated round-robin across domains |
| Disruptions | Host-link interruption/restoration; OVS bridge deletion/recreation; destination host move to another switch port; controlled controller stop/start; SIGKILL of the controller service followed by externally initiated restart |
| Sample | Five blocks, 17 conditions per platform per block, 340 scheduled attempts |
| Ordering | Platform order randomized within each block with seed 20261043; condition order randomized with seed 20261001 and matched within a block |

When there are fewer new endpoint pairs than switches, some switches receive only the separate health-check traffic. Increasing the switch count therefore does not imply that every switch carries a measured new flow. The switch domains are not an interconnected routing topology.

DAIM uses the process-per-rule adapter because the current persistent adapter serves a single switch. The corrected, separate Section 5.6 experiment covers both adapters and the reactive Os-Ken baseline. No distributed implementation from Papers 2 or 3 is substituted for the Paper 1 Core.

## Environment and applications

One platform runs at a time in the same ARM64 Multipass VM, with four virtual CPUs and 4,090,548,224 bytes of reported guest memory. The environment snapshot, runtime/configuration outputs, service definitions, source hashes, native application bundle verification, and controller logs are retained. The Java services have a 1536 MiB maximum heap; all controller services have a 2500 MiB cgroup memory limit. These equal service caps do not imply equal runtime footprints or identical application semantics. No CPU pinning is used.

ONOS and ODL use restored native application class bytes. The verification compares every cached application class with the original backup; the manifest metadata can differ. ONOS uses a 300-second flow timeout. ODL uses its native L2Switch with the recorded drop-all setting disabled. Neither platform uses the earlier custom internal timing patch.

The DAIM and Os-Ken campaign wrappers supply a recorded DPID-to-bridge-name map. This avoids an unprivileged OVSDB lookup failure without modifying the learning policy or the DAIM C implementation. The DAIM service cgroup includes its external installation utilities. Access to each experimental bridge management socket is granted through the ubuntu group and disappears when that bridge is removed; global OVS permissions are not broadened.

Three pre-existing bridges, s3/s4/s5, were left untouched. They are a background-environment limitation, and the VM must not be described as an otherwise empty OVS instance. Host monitoring records CPU, memory-pressure and swap outputs; recording these does not establish isolation or absence of interference.

The existing dedicated-lab controller datastores are retained. Restarting a platform process between blocks does not create a virgin datastore. Trials within a block also share process history except when a scheduled controller-failure condition restarts it. Fresh trial identities prevent reuse within the campaign, but do not erase application caches or historical controller state; these are limits on attributing differences solely to the current switch/flow count.

## Trial sequence and measurement

Each platform block starts a fresh controller session, waits up to 180 seconds for its listener, then waits a fixed 30 seconds. Trials allocate globally fresh DPID, MAC and IPv4 identities. A new topology connects to the controller, waits 10 seconds after connection, and uses a separate pair per switch for bounded health checks. Health-check initiation stops after its 20-second window, but an in-progress probe can finish later. Failure to reach health readiness is recorded, not silently discarded.

The measured service batch sends one ICMP echo request per fresh endpoint pair, concurrently, with a one-second response-wait timeout. ARP resolution and native application behaviour are included. Packet counts and process return codes are parsed together; complete stdout/stderr and probe start/end timestamps are retained. A batch duration spans submission of the probe tasks through collection of every result. It is not pure rule-installation latency, a saturation-throughput measurement, or a packet-jitter estimate.

Flow tables are saved before health traffic, before target traffic, after the batch and after a disruption where applicable. These dumps support audit but are not the endpoint for this external service metric. Each condition retains separate connection, health-readiness, cold-probe, baseline, fault-injection, recovery and instrumentation outcomes.

## Disruption definitions

All disruption conditions use one switch and one measured endpoint pair. A successful two-packet pre-fault baseline is required for interpreting recovery. The software still records subsequent events when the baseline fails; these are not eligible recovery successes or failures.

| Event | Procedure and recovery origin |
| --- | --- |
| Link | Bring the destination link down, retain a downtime probe, then start the recovery clock immediately before bringing it up |
| Switch | Delete the OVS bridge, retain a downtime probe, then start the clock before recreating the bridge and restoring trial-socket access |
| Host move | Move the destination to port 100 with its original address; start observation after attachment and before one gratuitous ARP announcement |
| Controlled controller restart | Stop the service, verify its cgroup is empty, probe existing and fresh destinations, then start the clock before requesting service restart |
| Controller crash | SIGKILL all service processes, verify the cgroup is empty, probe existing and fresh destinations, then start the clock before requesting service restart |

Controller recovery probes target the distinct previously unprimed destination. No forwarding rules are manually cleared or inserted to manufacture recovery. A successful probe must complete within 30 seconds of the defined restoration origin. Probe attempts and any late completion are retained. The time is an observed service-restoration bound at the probe resolution, not the exact instant of recovery.

Controlled stop and SIGKILL are distinct interventions. The preserved ONOS fwd source (`r5_onos_comparison_spike/fwd_patch_evidence/ReactiveForwarding.java.ORIGINAL_SOURCE`, `deactivate()`) explicitly invokes `flowRuleService.removeFlowRulesById(appId)`. Native application cleanup policy can therefore differ between graceful shutdown and a process kill. This source observation is not a per-trial causal trace, and existing-flow continuity must not be treated as an architecture-wide reliability ranking.

The host-move clock excludes the physical move operation itself. Controller restart is externally initiated; it is not automatic failover, standby promotion or distributed state recovery. Link and switch events are emulated host-link/OVS events, not physical network failures.

## Table labels and code identifiers

The manuscript tables use readable labels; the raw data, scripts and
`statistics.json` use the code identifiers below.

| Manuscript label | Code identifier | Procedure |
| --- | --- | --- |
| Link restored | `link_restore` | Host link brought down, then up |
| OVS bridge recreated | `switch_restart` | OVS bridge deleted, then recreated |
| Host moved | `host_move` | Destination host moved to port 100, original address kept |
| Controller restart | `controller_restart` | Controlled service stop, then externally initiated start |
| Controller crash (SIGKILL) | `controller_crash` | SIGKILL of all service processes, then externally initiated start |

## Resources and analysis

Controller cgroup CPU and current-memory snapshots bracket the measured cold batch. CPU differences are reported only when the service InvocationID is unchanged. They include child processes but exclude OVS and the probe harness; VM resource snapshots are separate. Current memory is not a per-trial peak. The retained systemd MemoryPeak value is a service-lifetime statistic and must not be relabelled as a trial peak.

The frozen analysis describes run-level success fractions, whole-batch successes, batch durations and resource measurements. Recovery rates use only baseline-valid, observed and verified fault cases. Successful recovery times are explicitly conditional on recovery within the window. Every scheduled attempt remains in the accounting, including setup errors, connection timeouts, readiness failures and non-recovery.

There are five scheduled observations per platform/condition. Nominal exact binomial intervals use the stated independent-run, constant-probability assumption; they are not adjusted for multiple conditions. Conditions share controller sessions, applications differ, and resource/history effects remain. The report therefore makes no architecture ranking or production-scale claim. Packet counts are descriptive, not independent replicates for significance tests.

## Collection amendments

The first eight records belong to the initial frozen collector. Record eight failed before the measured workload because its experimental management socket did not appear. It remains an instrumentation error, not a network-service failure, and is not replaced.

Amendment 01 changes the same per-switch OVSDB transaction from a PTY command string to an argv/pipe invocation, capturing return code and both output streams with a 20-second command bound. Separate diagnostics succeeded with both execution methods, so the original failure cause remains unresolved; PTY truncation is not established. A final diagnostic passed the 66-port, 32-pair case with the amended collector.

The first resume stopped before any new trial because the original parameter JSON had used the same key for a numeric recovery window and its prose description. Amendment 02 checks the immutable original source and its 30-second default, separates the description field, and preserves all prior records. Neither amendment changes the scheduled sample, workload, measurement boundaries or recovery window.

Continuation appends only unattempted schedule slots and verifies that the first eight raw records remain byte-for-byte unchanged. The original controller InvocationID is retained for the interrupted partial session. The frozen sources, amended sources, failed resume logs and separate diagnostics remain available. The final report must disclose that collection used an amended instrument; it must not claim one unchanged collector across all 340 slots.

## Remaining scope

This campaign supplies previously missing single-instance service comparisons, bounded scale/concurrency cases, resource accounting including subprocess children, and specified disruption/recovery cases. It does not supply hardware-switch measurements, maximum sustainable throughput, multi-controller state synchronization, automatic failover, or a distributed DAIM deployment. Those capabilities require a separately defined implementation and evaluation rather than relabelling single-Core results.

## Interpretation clarification during collection

Inspection of the first completed platform block found an ODL controller-crash case with successful communication to the new destination while the controller cgroup was already empty. A later successful probe in that case is not evidence of restoration after an observed interruption. The frozen analysis's `recovered` fields therefore describe successful post-action service observation; they cannot alone establish a preceding outage.

The collection procedure and frozen analysis remain unchanged. A separately labelled supplementary interpretation uses the saved downtime probe to distinguish continuing reachability from service observed after probe loss. For host movement, no probe occurs during detach/attach; the first post-move probe determines whether loss was observed during the subsequent observation period. No observed probe loss does not establish uninterrupted service between probes. This interpretive check was defined during collection, not before the first attempt, and must be identified as such in reporting.

## Completed collection and verification

All 340 scheduled attempts are retained: 339 procedures completed and one
setup error was not replaced. The post-collection audit checked 8,167 distinct
probe events, including an independent packet-count parse, and 5,617 flow reads
with zero reported consistency findings. The first eight records remain
unchanged. All 36 source hashes matched the applicable amendment after collection;
the four experimental services stopped and no scheduled experimental bridge
remained. The three pre-existing bridges remained untouched.

The host monitor retained 787 samples. Memory-pressure code 2 was present in
all samples, and host swap counters increased by 254,480 input pages and
233,098 output pages (16,384 bytes per page). Host CPU idle ranged from 19.90%
to 88.20%. These are whole-window observations, including pauses and diagnostics;
they cannot isolate a controller's cost or explain an individual failure.
No attempt was discarded based on the later resource summary.

The numerical results, eligibility denominators, separate outage interpretation
and limitations are in `R5_SERVICE_CAMPAIGN_RESULTS_20261001.md`. The local
artifact reproduces five derived outputs byte-for-byte. This is an author-side
package check, not independent laboratory reproduction or a public DOI release.
