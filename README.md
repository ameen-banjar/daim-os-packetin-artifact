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
  the switch-adapter interface, a mock adapter, an OVS adapter, a NO_RULE
  learning application, and their unit/concurrency tests.
- `network/` — the real Os-Ken OpenFlow 1.3 controller and ctypes bridge
  (`daim_bridge_controller.py`, `daim_core_bridge.py`), the two-switch
  Packet-In integration experiment, and the Stage-2 adapter-overhead
  microbenchmark scripts.
- `environment/` — the Lima/QEMU Ubuntu 24.04 VM manifest and provisioning
  script used for all network-integration evidence.
- `analysis/paper1_analysis.py` — computes bootstrap 95% confidence intervals
  from the raw microbenchmark data and generates all five paper figures.
- `results/` — raw CSV/JSON observations, derived summaries, and the
  generated figures, organised the same way the paper cites them
  (`results/network/`, `results/paper1/`, `results/raw/`, `results/summary/`,
  `results/stage2_calibration/`).
- `logs/` — compiler, build, and provisioning logs for the recorded runs.
- `src/interface_probe.c` — the ABI/constant probe used for the header
  conformance evidence (Section 6.1 of the paper).
- `docs/DATA_DICTIONARY.md` — column definitions for the interface-probe CSV.

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

# Recompute statistics and regenerate all five figures from the raw CSV
python3 analysis/paper1_analysis.py
```

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
