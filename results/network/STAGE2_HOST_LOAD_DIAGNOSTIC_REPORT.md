# Host-Load Diagnostic for the 64-Switch Tail

Date: 20 July 2026
Environment: Ubuntu 24.04 ARM64 (primary `daim-lab-qemu` VM), Open vSwitch
3.3.4, Mininet 2.3.0, Os-Ken 2.6.0
Evidence level: `measured_emulation`

## What this was for

`STAGE2_FULL_COMPARE_PAIRED_REPORT.md` (task #19) found that
`direct_osken`'s install time at 64 switches is heavy-tailed (27/30
trials within 10.4-13.9 ms, 3 trials at 34.3/61.8/151.0 ms) and left the
cause unidentified, naming a host-load trace as necessary future work.
This experiment adds that trace: 120 real trials (30 repetitions x 4
modes, mode order freshly shuffled within each repetition block, size=64
only, reusing `stage2_full_compare.py`'s trial-execution code unchanged)
each recorded `/proc/loadavg`'s 1-minute average immediately before and
immediately after the trial, alongside the existing install-time fields.

## Result: the tail did not recur in this sample, and load does not explain ordinary variation

All 120 trials passed their connectivity check. Unlike task #19's run of
the same (mode, size) conditions, **no trial in this 120-trial sample
exceeded 1.22x its own mode's median** -- `direct_osken`'s own
max-to-median ratio here was 1.10x, far short of the 13.2x task #19
recorded for the same mode and size. The heavy tail this experiment set
out to explain simply did not occur this time.

Because no tail trials occurred, the planned tail-vs-non-tail load
comparison could not be run; what can be reported is the correlation
between install time and load average across ordinary (non-tail)
variation. It is weak to negligible for every mode (Pearson r: -0.002 for
`daim_process_per_rule`, +0.095 for `daim_persistent`, +0.093 for
`direct_ovs_cli`, -0.197 for `direct_osken`; overall r = -0.039 across
all 120 trials). None of these support 1-minute load average as a driver
of ordinary trial-to-trial variation at this size. Full data and a
scatter plot are in `stage2_host_load_diagnostic_statistics.json` and
`stage2_host_load_diagnostic.png`.

## What this does and does not establish

**It does not identify the cause of the tail task #19 found, and it
cannot rule out host load as a contributor to that tail specifically**,
because the tail is rare enough (task #19: 3/30 trials, 10%, for one
mode at one size) that a fresh 120-trial sample of the same conditions
can miss it entirely -- which is itself the most informative result
here: it is direct, repeated confirmation of how intermittent the
phenomenon is, consistent with (not contradicting) task #19's and the
independent-rerun's (`INDEPENDENT_CLEAN_RERUN_REPORT.md`) shared finding
that this artifact's 64-switch measurements carry more uncertainty than a
handful of repetitions can characterise. **It does establish that, absent
a tail event, 1-minute load average is not a useful predictor of this
harness's ordinary install-time variation** -- a narrower, still useful,
negative result.

## Claim boundary

`/proc/loadavg`'s 1-minute average is a coarse, smoothed metric; it may
be insensitive to a short-lived spike that a per-trial CPU/scheduler
trace (e.g. `sar` at sub-second resolution, or per-core utilisation
during the trial itself rather than a smoothed average before/after it)
would catch. Building that finer-grained trace, and repeating this
diagnostic until a tail event actually occurs within it, remain open
work; this experiment narrows what "host-load trace" can mean here but
does not complete it.
