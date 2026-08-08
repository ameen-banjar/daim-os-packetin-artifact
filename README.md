# DAIM-OS Packet-In Artifact

Reproducibility artifact for the paper:

**"Reconstructing the DAIM-OS Table-and-Signal Control Path: An Executable
OpenFlow 1.3 Artifact and Evaluation"** — Ameen Banjar (2026).

This repository contains only the code, raw data, logs, and figures cited by
that paper. It is deliberately scoped to that single paper: the author's
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
  Packet-In integration experiment, the 4-way adapter-overhead
  microbenchmark (`stage2_full_compare.py` and its randomised/paired
  variant), the reactive Packet-In stage-latency breakdown
  (`packetin_latency_breakdown.py`), the sustained-load control-plane
  profile (`control_plane_load_profile.py`), and the host-load diagnostic
  (`stage2_host_load_diagnostic.py`).
- `environment/` — Lima/QEMU VM manifests and the provisioning script used
  for all network-integration evidence: the primary ARM64 environment
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

## Post-review evidence (in response to external Q1-standard review)

The following experiments were added after an external review of an
earlier draft; each closes a specific, named threat to validity, and each
is documented with its own report under `results/network/`:

- Persistent OpenFlow 1.3 adapter and a 4-way (process-per-rule/
  persistent/direct-`ovs-ofctl`/DAIM-free-Os-Ken) overhead comparison
  (`STAGE2_FULL_COMPARE_REPORT.md`).
- 8-stage, 60-trial randomised-order latency breakdown of the reactive
  Packet-In path (`PACKETIN_LATENCY_BREAKDOWN_REPORT.md`).
- Sustained multi-sender throughput/CPU/control-traffic profile, at both
  5 and 30 repetitions per mode (`CONTROL_PLANE_LOAD_PROFILE_REPORT.md`).
- A randomised-order, paired, 30-repetition (480-trial) re-run of the
  4-way comparison, which replicates the original finding at small/medium
  scale and revises it at the largest tested size due to a heavy-tailed
  variance the original 5-repetition sample could not detect
  (`STAGE2_FULL_COMPARE_PAIRED_REPORT.md`).
- The same comparison on a second, independently built x86-64 environment
  (`STAGE2_FULL_COMPARE_X86_64_REPORT.md`) and an independent clean rerun
  on a third, unrelated VM (`INDEPENDENT_CLEAN_RERUN_REPORT.md`); both
  independently reproduce the large-scale fragility finding above.
- A host-load diagnostic that could not identify the cause of that
  fragility, but independently confirms how intermittent it is
  (`STAGE2_HOST_LOAD_DIAGNOSTIC_REPORT.md`).

## Reproducing the results

Inside the provisioned Ubuntu 24.04 ARM64 VM (see `environment/`):

```sh
# Core, adapter, and learning-application tests (strict + sanitizer builds)
make -C implementation clean check

# Stage 1: two-switch OVS integration
sudo bash network/run_stage1.sh

# Packet-In -> NO_RULE -> installed OVS rule, with a real Os-Ken controller
sudo python3 network/run_daim_bridge_smoke.py

# Stage 2: matched adapter-overhead microbenchmark (8/16/32/64 switches)
sudo bash network/run_stage2_final_local.sh

# Recompute statistics and regenerate all five original figures from the raw CSV
python3 analysis/paper1_analysis.py

# 4-way comparison, reactive-path latency breakdown, sustained-load profile,
# and their randomised/paired/host-load-diagnostic variants (all invocations
# need PATH preserved through sudo -- see network/README.md):
sudo env "PATH=$PATH" python3 network/stage2_full_compare.py
sudo env "PATH=$PATH" python3 network/packetin_latency_breakdown.py
sudo env "PATH=$PATH" python3 network/control_plane_load_profile.py
sudo env "PATH=$PATH" python3 network/stage2_full_compare_paired.py       # 480 trials, ~75 min
sudo env "PATH=$PATH" python3 network/stage2_host_load_diagnostic.py      # 120 trials, ~25 min

# Corresponding analyses (one script per experiment above, same naming)
python3 analysis/stage2_full_compare_analysis.py
python3 analysis/packetin_latency_breakdown_analysis.py
python3 analysis/control_plane_load_profile_analysis.py
python3 analysis/stage2_full_compare_paired_analysis.py
python3 analysis/stage2_host_load_diagnostic_analysis.py
```

The second-environment (`stage2_full_compare_x86_64_analysis.py`) and
independent-clean-rerun evidence require provisioning a second VM from
`environment/daim-lab-qemu-x86_64.yaml` or `environment/daim-lab-qemu.yaml`
respectively; see the corresponding reports under `results/network/` for
the exact steps taken.

## Evidence labels

Every raw-data file and report in this artifact carries one of the evidence
labels used throughout the paper:

- `measured`: produced by compiling and running the published C headers.
- `measured_emulation`: produced by a real Linux/Open vSwitch/Mininet
  execution recorded in this repository.

No pilot-model, simulated, or historical (2013-2018) numerical result is
included in this artifact; every number here was produced for this paper.

## License

Apache License 2.0 (matching the DAIM-OS specification). See `LICENSE`.

## Citation

See `CITATION.cff`. If you use this artifact, please also cite the paper
once published, and the DAIM-OS specification (DOI above) that it implements.

Version 1.1.0 is archived on Zenodo: https://doi.org/10.5281/zenodo.21855229.
The version-independent concept DOI is https://doi.org/10.5281/zenodo.21441309.
