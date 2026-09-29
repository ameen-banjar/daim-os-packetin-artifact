# Historical raw data

## `control_plane_load_profile_ORIGINAL_5REP_raw.csv`

The original Section 5.7 finite-burst dataset (5 repetitions per adapter
mode, 10 trials total). Superseded on the live path
(`../control_plane_load_profile_raw.csv`) by Section 5.10's 30-repetition
rerun (60 trials) on 2026-07-21; both experiments write to the same
filename, so only the most recent sample is present at the live path.

**All published numbers in this paper's Section 6.2.2 table (throughput,
controller CPU time, controller max RSS, encoded Flow-Mod payload, flows
installed) are computed from the current 30-repetition sample at the live
path, not from this historical file.** This file exists only so the
original 5-repetition sample remains inspectable; it is not read by any
analysis script.

**Provenance:**
- Source: git blob `a254999e85cbe21140d84b20b0164b0e8cbcbe91`, extracted
  from commit `48a3544c059e43de76091def57f5621d79723bf7` (2026-07-20) in
  the paper's working repository (not this artifact repository's own
  history), via `git show 48a3544:experiments/results/network/control_plane_load_profile_raw.csv`.
- SHA-256 of the extracted file:
  `f2b10f92222f56a8dcd4eec587f443c2244a44da4694a28f3c73c6970d6aff3c`
  (verified identical to the blob's own content hash at extraction time,
  and to this file after copying into this repository).
- Extracted 2026-09-29 during a statistical audit of the Major Revision
  response for COMNET-D-26-05698.

**Limits of this record:** comparing every row of this file against every
row of the current 60-trial file (600 comparisons across
`throughput_installs_per_s`, `cpu_s`, `elapsed_s`) found zero exact
matches, which rules out this file's rows being literally duplicated
inside the current one. It does not rule out other forms of data reuse,
and does not establish statistical independence between the two
collection sessions -- no timestamp column exists in either CSV, and no
separate run log survives for this experiment to establish that further
beyond the two collection commits' timestamps (2026-07-20 09:25 and
2026-07-21 08:35).
