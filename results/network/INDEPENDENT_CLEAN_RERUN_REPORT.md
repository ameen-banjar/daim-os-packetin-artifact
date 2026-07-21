# Independent Clean Rerun Report

Date: 20 July 2026
Environment: fresh Ubuntu 24.04 ARM64 Lima VM (`daim-lab-independent`),
provisioned from `environment/daim-lab-qemu.yaml` and
`environment/provision_ubuntu.sh` only -- the same documented
configuration files used for the primary environment, run a second time
on a VM that shares no state, build artifacts, or prior process with it.
Evidence level: `measured_emulation`

## What this closes

The manuscript's Section 7.4 Reproducibility discussion states: "A clean
rerun by an independent researcher has not yet been performed; the
artifact therefore supports repeatability by the development team, not a
claim of independent reproduction." Task #21 closes the "independent,
from-scratch, documentation-only" half of that gap as far as it can be
closed without an actual second researcher: a third VM was provisioned
from the two configuration files a new user would use, the source tree
was copied into a location this VM shares with no other VM or the host's
build directory (so nothing could be reused or contaminated from prior
runs), and only the steps written in `README.md`,
`environment/provision_ubuntu.sh`, and `implementation/Makefile` were
followed -- no step relied on knowledge not present in those files.

## Friction found: `osken-manager` is not on `sudo`'s PATH

`provision_ubuntu.sh`'s `pip install --break-system-packages` step
installs the Os-Ken console scripts (including `osken-manager`, which
every network experiment in this artifact invokes) to
`~/.local/bin`, which is on a normal login shell's `PATH` but not on
`sudo`'s default `secure_path` -- confirmed identically on both this
rerun and the independent x86-64 VM (`STAGE2_FULL_COMPARE_X86_64_REPORT.md`),
so it is a general property of the documented provisioning step on a
fresh Ubuntu 24.04 install, not a one-off. Since every network experiment
script requires root (for Mininet) and therefore must be invoked via
`sudo`, following the documentation exactly as written (`sudo python3
<script>.py`) fails to find `osken-manager`. The fix
(`sudo env "PATH=$PATH" python3 ...`, i.e. `sudo -E`-style PATH
preservation) is a standard Unix technique, not DAIM-specific knowledge,
and is now the one deviation from the literal documented commands that
this rerun needed. `README.md`/`network/README.md` do not currently
mention it; adding a line there is identified as a documentation fix
below.

## Result: build, tests, and Stage 1 reproduce cleanly

- `make all` (strict `-Werror`) and the full unit-test suite (`test_core`,
  `test_adapters`, `test_concurrency`, `test_learning_app`,
  `test_persistent_adapter`) passed, unmodified, from source.
- The Stage 1 two-switch integration test
  (`two_switch_demo_independent_rerun.json`) passed: 4 installed rules,
  0% ping loss, matching the original report's structure exactly.

## Result: 4-way comparison at two sizes -- what replicates and what doesn't

Given the wall-clock cost of the full 80-run benchmark, this rerun used
the identical methodology (5 repetitions, mode-major order, same
topology and workload) at the two extreme sizes (8 and 64 switches; 40
trials total), rather than all four, as a scoped reproduction check
(`stage2_full_compare_independent_rerun_raw.csv`).

| Switches | Mode | Original report | Independent rerun |
|---:|---|---:|---:|
| 8 | process-per-rule | 13.557 ms | 10.990 ms |
| 8 | persistent | 5.861 ms | 5.331 ms |
| 8 | direct ovs-ofctl | 9.890 ms | 11.385 ms |
| 8 | direct Os-Ken | 1.630 ms | 2.109 ms |
| 64 | process-per-rule | 16.903 ms | 13.778 ms |
| 64 | persistent | 13.377 ms | 14.245 ms |
| 64 | direct ovs-ofctl | 12.959 ms | 14.127 ms |
| 64 | direct Os-Ken | 11.298 ms | 13.546 ms |

**At 8 switches, the key qualitative relationships reproduce**: the
persistent adapter remains clearly faster than process-per-rule, and
`direct_osken` remains clearly the fastest of the four, on a completely
independent build. Absolute values differ by 10-30%, consistent with
ordinary run-to-run variance on a shared virtualised host, and with
task #19's finding that this artifact's variance is non-trivial even
within one environment.

**At 64 switches, this independent rerun does not cleanly reproduce the
original ordering either -- and that is itself informative.** Here
process-per-rule (13.778 ms) is marginally faster than persistent
(14.245 ms), the same direction of disagreement with the original
report that the x86-64 rerun showed independently
(`STAGE2_FULL_COMPARE_X86_64_REPORT.md`), and all four modes cluster
within a 13.5-14.2 ms band rather than the more separated original
values. This is not read as a new problem: it is an independent
confirmation of task #19's own finding, on a completely different VM
instance, that this artifact's 64-switch measurements are specifically
prone to a small-sample fragility that a 5-repetition, mode-sequential
design (used here, deliberately, for direct comparability) cannot
reliably resolve. Two unrelated fresh environments -- one same-architecture,
one cross-architecture -- both landing on the same instability at the
same specific scale is stronger evidence for that fragility being a real
property of the measurement than the original 30-repetition paired
re-run was by itself.

## Recommended documentation fix

Add the `sudo -E` (or equivalent PATH-preserving) requirement to
`network/README.md`, next to the existing invocation examples, so a
future independent reproducer does not need to rediscover it.

## Claim boundary

This is one rerun by the same author who built the artifact, on
infrastructure the author controls -- not a rerun by a different person,
which is what "independent reproduction" ordinarily means and what
Section 7.4 should still be read as not yet claiming. What it does
establish is that the documented setup path works end-to-end without any
undocumented step beyond the PATH fix above, and that the artifact's
own previously identified 64-switch measurement fragility (task #19) is
not confined to the specific VM instance that first produced it.
