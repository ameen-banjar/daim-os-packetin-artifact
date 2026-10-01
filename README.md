# DAIM-OS Packet-In Artifact

> **Local revision candidate, 1 October 2026:** A corrected Section 5.6
> sample is documented in [Corrected Packet In experiment](docs/CORRECTED_PACKETIN_20261001.md).
> Historical capture and ping-check defects limit the older dataset; its
> results must not be confused with the corrected sample. These local
> additions are not yet included in the published v1.1.0 DOI snapshot.
> The additional 340-attempt service campaign is documented in
> [its results](docs/R5_SERVICE_CAMPAIGN_RESULTS_20261001.md) and
> [reanalysis instructions](network/R5_SERVICE_CAMPAIGN_REPRODUCTION.md).
> Manuscript/response integration and public release remain pending.

Artifact lineage — original submission title:

**"Reconstructing the DAIM-OS Table-and-Signal Control Path: An Executable
OpenFlow 1.3 Artifact and Evaluation"** — Ameen Banjar (2026).

This local candidate retains the original Paper 1 evidence and adds corrected
and additional experiments awaiting consistent manuscript integration. It is
scoped to that single paper: the author's
related work on autonomous link recovery, cross-environment reproducibility,
policy-conflict resolution, and intent assurance are separate, independent
contributions with their own artifacts, not included here.

## Relationship to the DAIM-OS specification

This artifact implements a declared subset of the published DAIM-OS v1.0.0
interface specification:

- Specification repository: https://github.com/ameen-banjar/DAIM-OS
- Specification DOI: https://doi.org/10.5281/zenodo.21426560

A pinned, vendored copy of the specification headers used to build this
artifact is included under `vendor/DAIM-OS-v1.0.0/` for reproducibility (so
this repository can still be built even if the specification repository
changes in the future). The canonical, citable specification is the
repository and DOI above.

## What is in this repository

- `implementation/` — the C core (five writable DAIM tables, mutex-protected),
  the switch-adapter interface, a mock adapter, an OVS adapter (process-per-
  rule and a from-scratch persistent OpenFlow 1.3 adapter,
  `ovs_persistent_adapter.c`), a NO_RULE learning application, and their
  unit/concurrency tests.
- `network/` — the real Os-Ken OpenFlow 1.3 controller and ctypes bridge
  (`daim_bridge_controller.py`, `daim_core_bridge.py`), the two-switch
  Packet-In integration experiment, the historical four-path timing experiment with different timing
  boundaries (`stage2_full_compare.py` and its randomised/paired variant), the reactive Packet-In stage-latency breakdown
  (`packetin_latency_breakdown.py`, plus the DAIM-free
  `osken_reactive_baseline_controller.py` baseline it compares against),
  the sustained-load control-plane profile
  (`control_plane_load_profile.py`), and the host-load diagnostic
  (`stage2_host_load_diagnostic.py`).
- `environment/` — Lima/QEMU VM manifests and the provisioning script used
  for the original network-integration evidence: the primary ARM64 environment
  (`daim-lab-qemu.yaml`) and a second, independently built x86-64
  environment (`daim-lab-qemu-x86_64.yaml`, run under QEMU TCG emulation
  since no physical x86-64 machine was available). See `network/README.md`
  for a `sudo`/PATH friction found while provisioning fresh VMs from these
  files, and its fix.
- `analysis/` — bootstrap-confidence-interval and paired/median-robustness
  analysis scripts for every experiment above, each generating its own
  figure(s) from the corresponding raw CSV.
- `results/` — raw CSV/JSON observations, derived summaries, per-experiment
  reports, and the generated figures, organised the same way the paper
  cites them (`results/network/`, `results/paper1/`, `results/raw/`,
  `results/summary/`, `results/stage2_calibration/`).
- `logs/` — compiler, build, and provisioning logs for the recorded runs.
- `src/interface_probe.c` — the ABI/constant probe used for the header
  conformance evidence (Section 6.1 of the paper).
- `docs/DATA_DICTIONARY.md` — column definitions for the interface-probe CSV.

## Historical evidence and its interpretation limits

The original reports and raw records remain unchanged for provenance. Later
source inspection found that the old reactive capture could select the warm-up
packet, that several historical ping-success predicates accepted total loss,
and that the four-path benchmark measured different spans without traversing
DAIM Core/ctypes. Recomputing old statistics does not repair those defects.
See [the validity note](docs/HISTORICAL_DATA_VALIDITY_20261001.md).

The randomized four-path rerun changed both sample size and ordering. Its
changed conclusion cannot be attributed solely to either factor. The clean-VM
and second-architecture reruns were performed by the author, not independently
replicated by another research group. Their historical filenames are retained.

## Corrected and additional local evidence

- [Corrected Section 5.6](docs/CORRECTED_PACKETIN_20261001.md): 90 scheduled
  attempts, full packet identity and full-rule observation, with a
  [standalone results report](docs/S56_CORRECTED_RESULTS_20261001.md).
- [Additional service campaign](docs/R5_SERVICE_CAMPAIGN_RESULTS_20261001.md):
  340 scheduled attempts across DAIM process-per-rule, Os-Ken, ONOS and ODL;
  339 completed procedures and one retained setup error. This covers bounded
  switch/endpoint-pair counts, resources and five disruption procedures.
  Completion is not service success. The host experienced memory pressure and
  swapping, native applications differ, and n=5 per condition is exploratory.
- The existing 60-attempt controlled-restart study is a separate experiment;
  it is not pooled with the additional campaign or reclassified as failover.

The additional campaign used the recorded Multipass VM and native-controller
configuration, not the original Lima environment. Its complete raw records and
logs are included. `results/network/r5_service_campaign_20261001/package_export.json`
explicitly lists eight unused
peer/distributed source files omitted from the private frozen source inventory,
plus the local monitor stop sentinel. Those unused sources were not linked into
the Paper 1 library. The original source manifests retain their hashes for
provenance; the complete private snapshot remains in the working repository.
No raw trial or host-monitor record is omitted by this source selection.
Separate precollection diagnostic records are retained in
`results/network/r5_precollection_evidence_20261001/`, with their own explicit
export inventory; the density-check archive is retained alongside it. Failed
diagnostics and the superseded draft plan are not part of the official sample.
[Package reanalysis verification](docs/PACKAGE_REANALYSIS_20261001.json) records
five byte-identical derived outputs and five passing parser/matcher tests.

## Reproduction

For corrected-data analysis and new network collection, use the separate
[Section 5.6 instructions](docs/CORRECTED_PACKETIN_20261001.md) and
[service-campaign instructions](network/R5_SERVICE_CAMPAIGN_REPRODUCTION.md).
The latter distinguish reanalysis from provisioning native controllers and
collecting a new sample. Network collection is not performed by analysis calls.
Working-repository path prefixes in preserved provenance documents describe
that original layout; package files are under `network/`, `analysis/` and
`results/` here.

The old collectors remain as historical source. Their defective success gates
must not be used to gather a newly validated sample. Historical reanalysis can
be performed in a disposable copy because those scripts use fixed output paths:

```sh
python3 analysis/stage2_full_compare_analysis.py
python3 analysis/packetin_latency_breakdown_analysis.py
python3 analysis/control_plane_load_profile_analysis.py
python3 analysis/stage2_full_compare_paired_analysis.py
python3 analysis/stage2_host_load_diagnostic_analysis.py
```

Matching an old output establishes numerical reproducibility only. It does not
validate the old packet identity, connectivity claims or comparison boundaries.
The unchanged single-Core tests remain available through
`make -C implementation clean check` on a supported build environment.

## Evidence labels

The historical documentation uses these evidence-origin labels:

- `measured`: produced by compiling and running the published C headers.
- `measured_emulation`: produced by a real Linux/Open vSwitch/Mininet
  execution recorded in this repository.

The new network campaigns are emulated executions, not physical-switch tests.
Their records use the explicit outcome fields and provenance described in their
protocols; not every record has a literal evidence-label field. An origin label
does not establish measurement validity. Historical limitations, diagnostic
fixtures and the new validated checks remain explicitly distinguished.

## License

Apache License 2.0 (matching the DAIM-OS specification). See `LICENSE`.

## Citation

See `CITATION.cff`. If you use this artifact, please also cite the paper
once published, and the DAIM-OS specification (DOI above) that it implements.

Version 1.1.0 is archived on Zenodo: https://doi.org/10.5281/zenodo.21855229.
The version-independent concept DOI is https://doi.org/10.5281/zenodo.21441309.
