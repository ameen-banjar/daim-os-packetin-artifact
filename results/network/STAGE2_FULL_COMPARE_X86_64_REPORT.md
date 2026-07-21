# Second Environment: x86-64 4-Way Comparison Report

Date: 20 July 2026
Environment: Ubuntu 24.04 x86-64 (QEMU TCG software emulation on the same
ARM64 host as the primary environment; no physical x86-64 machine was
available), Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

The manuscript's Section 8 External Validity threat records: "All network
measurements used one ARM64 QEMU VM... Results may differ on x86-64, bare
metal, hardware switches, containers, or another OVS version." Task #20
addresses the x86-64 half of that directly: an independently provisioned
second environment (`environment/daim-lab-qemu-x86_64.yaml`, mirroring
the primary `daim-lab-qemu.yaml` except for architecture and image),
built from a local, non-shared copy of the source tree (so this VM's
build cannot interact with the primary VM's), running the identical
`stage2_full_compare.py` benchmark: 80 real trials, same four modes, same
four sizes, same 5-repetition, mode-major methodology as the original
Section 6.3.1 report, for direct comparability. All 80 trials, plus the
Stage 1 two-switch integration smoke test and the full unit/sanitizer
test suite, passed with 0 failures on x86-64.

## Caveat: TCG emulation, not a physical second architecture

No physical x86-64 machine was available. This host is Apple Silicon
(ARM64); the x86-64 guest therefore runs under QEMU's software (TCG)
instruction-set emulation rather than hardware-accelerated virtualisation
(the primary environment uses `accel=hvf`, hardware acceleration, since
guest and host architecture match there). A single-trial calibration
before committing to the full run measured 6.8x-17.8x inflation in
per-switch install time depending on mode, and roughly 3.4x inflation in
total wall-clock trial time (topology setup/teardown is not as
CPU-emulation-sensitive as the install calls themselves). **Absolute
install times from this environment are therefore not directly
comparable to the primary environment's** and are not reported as such;
the informative comparison is whether the same architectural mechanisms
produce the same *direction*, and roughly the same *relative magnitude*,
of effect.

## Result: replicates at small/medium scale, diverges at 64 switches

Mean install time ratios (persistent adapter relative to the other two
comparison modes), from each environment's own 5-repetition sample; full
per-mode-size data in `stage2_full_compare_x86_64_statistics.json`.
Figure plots both environments' mean install times by mode and size on
independent y-axes (`stage2_full_compare_x86_64.png`).

| Switches | persistent/process-per-rule (ARM64) | persistent/process-per-rule (x86-64) | persistent/direct_osken (ARM64) | persistent/direct_osken (x86-64) |
|---:|---:|---:|---:|---:|
| 8  | 0.432 (faster) | 0.609 (faster) | 3.596 (slower) | 1.889 (slower) |
| 16 | 0.492 (faster) | 0.729 (faster) | 2.339 (slower) | 1.511 (slower) |
| 32 | 0.635 (faster) | 0.839 (faster) | 1.666 (slower) | 0.983 (~parity) |
| 64 | 0.791 (faster) | **1.142 (slower)** | 1.184 (slower) | **0.780 (faster)** |

**At 8, 16, and 32 switches, the direction of every comparison
replicates on x86-64**: the persistent adapter is still faster than
process-per-rule and still slower than a bare `direct_osken` connection,
at a somewhat smaller relative magnitude under emulation (consistent with
per-operation overhead already being inflated by TCG, proportionally
shrinking DAIM's own architectural contribution to the total). **At 64
switches, both ratios cross 1** -- on this x86-64 run, the persistent
adapter appears slightly *slower* than process-per-rule and slightly
*faster* than `direct_osken`, the opposite direction from the ARM64
result at that size.

**This is reported as a flagged, low-confidence observation, not a
confirmed architecture-dependent reversal.** Task #19's own randomised,
30-repetition, paired re-run of the ARM64 benchmark already established
that this artifact's 64-switch measurements are specifically prone to a
heavy-tailed variance that a 5-repetition, mode-sequential sample --
exactly what this x86-64 run also is -- cannot reliably characterise: the
ARM64 5-repetition sample's own 64-switch numbers did not survive a
properly powered re-run. Applying that same caution here, the honest
statement is that this single 5-repetition x86-64 sample shows the
64-switch pattern crossing over, not that it has established the
persistent adapter is unreliable specifically on x86-64 at that size. A
randomised, 30-repetition, paired re-run on x86-64, mirroring task #19's
design, would be needed to distinguish a genuine architecture effect from
the same kind of small-sample tail risk already documented on ARM64; it
was not run here given TCG's wall-clock cost (an estimated 4-5 hours for
480 trials at the observed ~3.4x slowdown, versus 74 minutes on ARM64).

## Other x86-64 results

- **Build and tests**: the strict `-Werror` build and the full unit-test
  suite (`test_core`, `test_adapters`, `test_concurrency`,
  `test_learning_app`, `test_persistent_adapter`) passed under both the
  normal build and ASan+UBSan, from source, unmodified.
- **Stage 1 two-switch integration**: passed (`two_switch_demo_x86_64.json`)
  -- 4 installed rules, 0% ping loss, matching the original ARM64 result's
  structure exactly.
- **Toolchain**: identical OVS (3.3.4), Mininet (2.3.0), Os-Ken (2.6.0),
  Clang (18.1.3), and GCC (13.3.0) versions to the primary environment.
  Kernel point-release differs (6.8.0-41-generic here vs.
  6.8.0-136-generic on the primary VM), an expected consequence of
  `apt-get install` resolving Ubuntu 24.04's rolling package set at a
  different provisioning date, not a deliberate environment choice.

## Claim boundary

This is not evidence about a physical x86-64 machine, only about a
second, independently built, software-emulated x86-64 guest. The
64-switch divergence is reported as a candidate finding requiring a
higher-powered replication, not as an established result; see task #19's
own report for why 5 repetitions at this specific scale are known to be
unreliable in this artifact.
