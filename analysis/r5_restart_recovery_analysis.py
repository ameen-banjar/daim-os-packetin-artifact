#!/usr/bin/env python3
"""Analysis for the R5 restart-recovery official sample (30 blocks x 2
arms = 60 trials, 01_DAIM_OS_Implementation/R5_RESTART_RECOVERY_PROTOCOL.md
Section 11). No new experiment -- reads
experiments/results/network/r5_official_sample.jsonl as collected (that
raw file is left untouched; see the "evidence_level" note below).

Revised after direct review of the first version's output:
- The block-bootstrap CI for an all-30/30-success recovery rate is
  degenerate (resampling an all-success sample always yields 100%), so
  it no longer reports that CI for the rate. The rate is reported as a
  plain count (30/30), with an exact Clopper-Pearson binomial CI offered
  separately and explicitly caveated (assumes independent trials and a
  constant success probability within this setup -- an assumption, not
  a property proven by the sample).
- Block-bootstrap resampling is used instead for what it is actually
  suited to here: the paired per-block recovery-time difference
  (persistent minus reactive_osken), which is not at a boundary.
- Reports raw ping-attempt counts for Q1/Q2 (300 each, not "60" or
  "120") alongside the per-trial summary counts.
"""
import json
import statistics as st
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/network/r5_official_sample.jsonl"
OUT = ROOT / "results/paper1/r5_restart_recovery_statistics.json"
SCHEDULE = ROOT / "results/network/r5_official_schedule.json"
MODES = ["persistent", "reactive_osken"]
SEED = 20260929  # same seed as the schedule; used here only for the block-bootstrap of paired differences
BOOTSTRAPS = 20000

EVIDENCE_LEVEL_NOTE = (
    "The raw records in r5_official_sample.jsonl carry "
    "evidence_level='measured_emulation_dry_run', inherited unchanged "
    "from the shared run_trial() function used by both the feasibility "
    "script and the official collector -- it was not updated when the "
    "official runner was built. The 60 records it labels ARE the "
    "official sample: they follow the frozen schedule "
    "(r5_official_schedule.json, seed 20260929) and the commit history "
    "documents the collection as official, not a dry run. This note is "
    "the documented correction; the raw file itself is left unmodified, "
    "per the standing rule not to silently rewrite collected records. "
    "This analysis's own output uses the correct label, "
    "'measured_emulation'."
)


def clopper_pearson_ci(successes, n, alpha=0.05):
    """Exact binomial CI. Implemented directly (no scipy dependency) for
    the two cases this sample actually produces: x=n (all successes) and
    the general case via a simple beta-quantile-free closed form is not
    elementary, so for 0<x<n this falls back to reporting None -- not
    needed here since both arms are 30/30, but guarded explicitly rather
    than silently returning a wrong number if that ever changes."""
    if n == 0:
        return None
    if successes == n:
        lower = (alpha / 2) ** (1 / n)
        return [float(lower), 1.0]
    if successes == 0:
        upper = 1 - (alpha / 2) ** (1 / n)
        return [0.0, float(upper)]
    return None  # not implemented for interior counts; not needed for this sample


def block_bootstrap_paired_diff(rows_by_block, rng):
    """Bootstrap over whole blocks (not individual trials) for the
    paired per-block difference persistent_time - reactive_osken_time,
    restricted to blocks where both arms recovered (both quantities
    must exist to form a difference)."""
    diffs_by_block = {}
    for b, entry in rows_by_block.items():
        p, o = entry.get("persistent"), entry.get("reactive_osken")
        if not p or not o:
            continue
        if not (p["valid_for_inference"] and o["valid_for_inference"]):
            continue
        if not (p.get("connectivity_recovery_observed") and o.get("connectivity_recovery_observed")):
            continue
        diffs_by_block[b] = (p["connectivity_recovery_time_from_restart_s"]
                              - o["connectivity_recovery_time_from_restart_s"])
    blocks = sorted(diffs_by_block.keys())
    diffs = [diffs_by_block[b] for b in blocks]
    n = len(diffs)
    if n == 0:
        return diffs_by_block, None, None
    draws = rng.choice(n, size=(BOOTSTRAPS, n), replace=True)
    medians = np.median(np.asarray(diffs)[draws], axis=1)
    ci = [float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))]
    return diffs_by_block, float(st.median(diffs)), ci


def iqr(values):
    if not values:
        return None, None
    a = np.asarray(sorted(values), dtype=float)
    return float(np.percentile(a, 25)), float(np.percentile(a, 75))


def main():
    rows = [json.loads(l) for l in RAW.open()]
    schedule = json.loads(SCHEDULE.read_text())
    rng = np.random.default_rng(SEED)

    rows_by_block = {}
    for r in rows:
        rows_by_block.setdefault(r["block"], {})[r["mode"]] = r

    summary = {
        "evidence_level": "measured_emulation",
        "evidence_level_note": EVIDENCE_LEVEL_NOTE,
        "source": str(RAW.relative_to(ROOT)),
        "schedule_seed": schedule["seed"],
        "n_blocks": schedule["n_blocks"],
        "recover_window_s": schedule["recover_window_s"],
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "bootstrap_note": (
            "Used only for the paired per-block recovery-time difference "
            "(resamples whole blocks). NOT used for the recovery-rate CI, "
            "which is degenerate for an all-success sample; an exact "
            "Clopper-Pearson binomial CI is reported for that instead."
        ),
        "per_mode": {},
    }

    for mode in MODES:
        mrows = [r for r in rows if r["mode"] == mode]
        invalid = [r for r in mrows if not r["valid_for_inference"]]
        valid = [r for r in mrows if r["valid_for_inference"]]

        q1_counts = [r["q1_success_count"] for r in valid]
        q2_counts = [r["q2_success_count"] for r in valid]
        q1_attempts_total = sum(len(r["q1_old_flow_during_downtime"]) for r in valid)
        q2_attempts_total = sum(len(r["q2_new_flow_during_downtime"]) for r in valid)
        q1_attempts_success = sum(c for c in q1_counts)
        q2_attempts_success = sum(c for c in q2_counts)

        recovered = [r for r in valid if r.get("connectivity_recovery_observed")]
        not_recovered = [r for r in valid if not r.get("connectivity_recovery_observed")]
        recovery_times = sorted(r["connectivity_recovery_time_from_restart_s"] for r in recovered)
        ready_gap_times = [r["connectivity_recovery_time_from_ready_s"] for r in recovered
                            if r.get("connectivity_recovery_time_from_ready_s") is not None]

        q25, q75 = iqr(recovery_times)
        n_valid = len(valid)
        n_recovered = len(recovered)
        exact_ci = clopper_pearson_ci(n_recovered, n_valid) if n_valid else None

        summary["per_mode"][mode] = {
            "n_trials": len(mrows),
            "n_valid": n_valid,
            "n_invalid": len(invalid),
            "invalid_reasons": [r["invalidation_reasons"] for r in invalid],
            "q1_old_flow_success_count_of_5_per_trial": q1_counts,
            "q2_new_flow_success_count_of_5_per_trial": q2_counts,
            "q1_total_ping_attempts": q1_attempts_total,
            "q1_total_ping_successes": q1_attempts_success,
            "q2_total_ping_attempts": q2_attempts_total,
            "q2_total_ping_successes": q2_attempts_success,
            "n_recovered": n_recovered,
            "n_not_recovered_within_window": len(not_recovered),
            "recovery_rate_observed": f"{n_recovered}/{n_valid}",
            "recovery_rate_exact_95ci_clopper_pearson": exact_ci,
            "recovery_rate_ci_caveat": (
                "Assumes independent trials and a constant success "
                "probability within this setup -- an assumption made to "
                "compute the interval, not a property this sample "
                "establishes on its own."
            ),
            # Explicitly conditional on success -- not_recovered trials are
            # excluded here, not defaulted to the window length.
            "recovery_time_from_restart_s_conditional_on_success": {
                "median": float(st.median(recovery_times)) if recovery_times else None,
                "iqr_25_75": [q25, q75],
                "min": recovery_times[0] if recovery_times else None,
                "max": recovery_times[-1] if recovery_times else None,
                "individual_values_sorted": recovery_times,
            },
            "recovery_time_from_ready_s_conditional_on_success": {
                "median": float(st.median(ready_gap_times)) if ready_gap_times else None,
                "min": min(ready_gap_times) if ready_gap_times else None,
                "max": max(ready_gap_times) if ready_gap_times else None,
            },
        }

    diffs_by_block, median_diff, diff_ci = block_bootstrap_paired_diff(rows_by_block, rng)
    n_pairs = len(diffs_by_block)
    all_positive = all(d > 0 for d in diffs_by_block.values()) if diffs_by_block else None
    summary["paired_block_difference_persistent_minus_reactive_osken_s"] = {
        "n_pairs": n_pairs,
        "median_diff_s": median_diff,
        "block_bootstrap_95ci_of_median_diff_s": diff_ci,
        "all_diffs_positive": all_positive,
        "individual_diffs_by_block": {str(b): d for b, d in sorted(diffs_by_block.items())},
        "reading": (
            "Every paired block shows the persistent adapter's observed "
            "connectivity recovery slower than the DAIM-free baseline's "
            "in this setup -- not generalised to DAIM's robustness or "
            "performance beyond this single-controller-restart scenario."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n")
    print(OUT)
    for mode in MODES:
        m = summary["per_mode"][mode]
        print(f"\n{mode}: n_valid={m['n_valid']}, recovery={m['recovery_rate_observed']}, "
              f"exact 95% CI={m['recovery_rate_exact_95ci_clopper_pearson']}")
        print(f"  Q1: {m['q1_total_ping_successes']}/{m['q1_total_ping_attempts']} ping attempts succeeded "
              f"(old flow, during downtime)")
        print(f"  Q2: {m['q2_total_ping_successes']}/{m['q2_total_ping_attempts']} ping attempts succeeded "
              f"(new flow, during downtime)")
        rt = m["recovery_time_from_restart_s_conditional_on_success"]
        print(f"  recovery_from_restart_s (conditional on success): median={rt['median']:.3f} "
              f"IQR=[{rt['iqr_25_75'][0]:.3f}, {rt['iqr_25_75'][1]:.3f}] "
              f"range=[{rt['min']:.3f}, {rt['max']:.3f}]")
    pd = summary["paired_block_difference_persistent_minus_reactive_osken_s"]
    print(f"\npaired per-block diff (persistent - reactive_osken): n={pd['n_pairs']}, "
          f"median={pd['median_diff_s']:.3f}s, 95% CI={pd['block_bootstrap_95ci_of_median_diff_s']}, "
          f"all positive={pd['all_diffs_positive']}")


if __name__ == "__main__":
    main()
