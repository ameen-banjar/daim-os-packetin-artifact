# Randomised-Order, Paired 4-Way Comparison Report (30 Repetitions)

Date: 20 July 2026
Environment: Ubuntu 24.04 ARM64, Open vSwitch 3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this closes

The manuscript's Section 8 Internal Validity threat records, against the
original 4-way comparison (`STAGE2_FULL_COMPARE_REPORT.md`, 5 repetitions
per mode-size condition, modes run sequentially): "matched adapter-overhead
modes were run sequentially rather than randomised... Randomising [the]
mode order, increasing its repetitions beyond five... remain future work
for that specific experiment." This experiment (task #19) does both, and
adds a paired analysis the original design could not support.

## Design

`stage2_full_compare_paired.py` reuses `stage2_full_compare.py`'s exact
trial-execution functions unchanged -- same linear topology, same
one-rule-per-switch workload, same four modes (`daim_process_per_rule`,
`daim_persistent`, `direct_ovs_cli`, `direct_osken`), same four sizes
(8/16/32/64 switches) -- and changes only the orchestration: 30
repetitions per (mode, size) instead of 5 (480 trials total, vs. 80
originally), and for each (size, repetition) pair the four modes' trials
are drawn in a freshly shuffled order (seeded, reproducible) and run
back-to-back, instead of the original mode-major loop. Because every
mode's trial for a given (size, repetition) is drawn from the same short
window, repetition index is a valid pairing key:
`stage2_full_compare_paired_analysis.py` computes paired differences
(persistent minus each of the other three modes, at each size) by
resampling repetition indices rather than treating each mode's 30 values
as an independent sample, which correctly propagates shared within-block
conditions (e.g. host load at that point in the run) into the interval,
and computes the same comparison on medians as a robustness check against
outlier sensitivity. All 480 trials completed their connectivity check
(0 ping failures).

## Result: a new finding this design surfaces that the original could not

**Install time is heavy-tailed in this shared VM, across every mode and
every size, not only in the mode the original 5-repetition design
happened to sample calmly.** The ratio of each condition's maximum
observed trial to its own median ranges from 1.5x to 5.7x for 29 of the
32 (mode, size) conditions -- consistent with ordinary host-scheduling
jitter -- but reaches **13.2x for `direct_osken` at 64 switches**: 27 of
its 30 trials fall in a tight 10.4-13.9 ms band (consistent with the
original report's 11.298 ms), but 3 trials took 34.3 ms, 61.8 ms, and
150.97 ms, all with a successful connectivity check. This tail was not
visible in the original 5-repetition, mode-sequential design; whether it
is specific or general could not have been distinguished from 5 samples,
and randomising 30 repetitions across all four modes is what surfaces it.
No host-load trace was collected in this artifact, so the cause (VM
scheduling, `eventlet`/Os-Ken startup contention, or something specific
to the bare-controller path) is not identified here; it is the collecting
of exactly that trace, named as future work in the original report, that
this finding now makes concretely necessary rather than precautionary.

## Result: mean-based comparison (same statistic as the original report)

n=30 per (mode, size); bootstrap 95% CIs, 20,000 resamples, seed 20260720.
Full data in `stage2_full_compare_paired_statistics.json`; Figure (left
panel) plots per-mode means with CI whiskers, (right panel) plots paired
mean differences against `daim_persistent`.

| Comparison (persistent minus...) | n=8 | n=16 | n=32 | n=64 |
|---|---:|---:|---:|---:|
| `daim_process_per_rule` | -9764 us [-12678, -7752], 0.40x | -8206 us [-10751, -6354], 0.45x | -5180 us [-7783, -2796], 0.65x | -1840 us [-4218, 1117], **CI crosses 0** |
| `direct_ovs_cli` | -7202 us [-10004, -4944], 0.47x | -4917 us [-6831, -3393], 0.58x | -2331 us [-4004, -879], 0.81x | 1779 us [-514, 4822], **CI crosses 0** |
| `direct_osken` | 4699 us [3548, 6509], 3.78x | 3575 us [3213, 3963], 2.15x | 2931 us [1270, 4879], 1.43x | -3370 us [-13486, 3134], **CI crosses 0** |

**At 8, 16, and 32 switches, every comparison replicates the original
report's direction and is statistically distinguishable from zero on 6x
the repetitions, with a similarly or slightly larger magnitude** (e.g.
persistent vs. process-per-rule: 2.53x here vs. 2.31x originally at
n=8). **At 64 switches, none of the three mean-based comparisons is
statistically distinguishable from zero under this design.** This
directly revises the original report's claim of a specific, still-
significant ratio at every tested size (1.26x vs. process-per-rule, 1.18x
slower than `direct_osken`, both at n=64): those point estimates came
from 5 repetitions each and this 30-repetition, randomised, paired design
shows the true variance at that size -- inflated by the tail described
above, present in `daim_process_per_rule` and `daim_persistent` too,
though less extremely than in `direct_osken` -- is too large to support a
mean-based claim of difference at n=64.

## Result: median-based robustness check

The same paired differences, computed on medians (bootstrap 95% CI of the
median difference), are far less sensitive to the handful of extreme
trials described above.

| Comparison (persistent minus...) | n=64 median diff | 95% CI |
|---|---:|---:|
| `daim_process_per_rule` | -2858 us | [-3156, -2706], significant |
| `direct_ovs_cli` | 430 us | [270, 671], significant |
| `direct_osken` | 1225 us | [678, 1541], significant |

**In typical-case (median) terms, all three comparisons remain
statistically distinguishable at 64 switches, in the same direction as
the original report**: persistent is still typically faster than
process-per-rule, and still typically slower than a bare `direct_osken`
connection -- but the *mean*-based test loses that signal at this size
because a small number of extreme trials (mostly in `direct_osken`, some
in the other three modes) inflate the variance faster than 30 repetitions
can shrink the confidence interval. The size of the typical-case gap is
also modest and revised downward from the original point estimates:
persistent's median advantage over process-per-rule narrows to 0.82x by
64 switches (originally reported as 1.26x, a mean-based figure), and its
median disadvantage against `direct_osken` is 1.12x (originally 1.18x,
also mean-based) -- directionally consistent, and now with an honestly
characterised, much wider uncertainty band around the mean-based
statistic specifically at this size.

## Claim boundary

This does not identify why `direct_osken` (or, less extremely, the other
three modes) occasionally takes several times longer than its typical
run at 64 switches; no CPU, memory, or scheduler trace was collected for
these trials. It measures the same one-rule-per-switch installation
workload as the original comparison, on the same single shared VM; it is
not evidence about behaviour on a quieter or dedicated host, nor a claim
that the underlying mechanism causing the tail is specific to any one
southbound path. The paired design's within-block time-proximity reduces
but does not eliminate slow, whole-run drift (a 480-trial run took
73.9 minutes; conditions at the start and end of that window are not
identical even though each individual (size, repetition) block is short).
