# Corrections log (release v1.1.1)

Three kinds of change are kept separate. None altered a measured value.

## A. Visual-only: figures redrawn (2026-10-02)

Figures 2, 6, 7, 8 and 9 (`results/paper1/paper1_architecture.png`,
`control_plane_load_profile.png`, `paper1_installation_time.png`,
`stage2_full_compare.png`, `stage2_full_compare_paired.png`) were redrawn
because labels or legends overlapped axes or data. The statistics JSON files
they read were not edited for this purpose. Previous hashes and per-figure
changes: [FIGURE_REVISION_20261002.md](FIGURE_REVISION_20261002.md).

## B. Textual scientific correction: `interpretation` field

`results/paper1/stage2_full_compare_statistics.json`, field `interpretation`.
Before: "Four-way isolation of process-spawn cost, DAIM Core/ctypes cost, and
native-controller OpenFlow cost ...". After: "Four-way comparison of
process-spawn cost, DAIM CLI-adapter wrapper cost (no DAIM Core or ctypes in
any path), and native-controller OpenFlow cost ...". Reason: neither
`daim_ovs_flow.c` nor `daim_persistent_flow.c` includes or calls DAIM Core or
the ctypes bridge; both call the switch-adapter layer directly. This is a
correction of meaning, not a visual change. The same wording was corrected in
the manuscript (Sections 1, 5.4, 6.3.1, 7.2, Table 3b, Figure 8 caption).

## C. Additive fields (no existing value changed)

`stage2_full_compare_statistics.json` gained `p95_ms`, `p99_ms`, `max_ms` per
summary row; `stage2_full_compare_paired_statistics.json` gained `p95_us`,
`p99_us`, `p95_diff_us`, `p99_diff_us`. Verified against the published v1.1.0
files: every field present in v1.1.0 has an identical value (0 changed, 16/16
summary rows; paired file 0 changed).

## D. Frozen source comment left in place

`network/stage2_full_compare.py`, header docstring, lines 2-6, says the
benchmark makes "process-spawn cost, DAIM Core/ctypes cost, and
native-controller OpenFlow cost" no longer confounded. **This statement is
wrong for the code as written**: in this benchmark the `daim_process_per_rule`
and `daim_persistent` paths run standalone C tools that do not call DAIM Core
or ctypes, so no Core/ctypes cost is measured. The file is the collector that
produced the recorded data and is kept byte-identical so the record is
unchanged. Read the comment together with section B and
[HISTORICAL_DATA_VALIDITY_20261001.md](HISTORICAL_DATA_VALIDITY_20261001.md).

## E. Other known limits recorded for readers

The historical collectors (`benchmark_stage2.py`, `stage2_full_compare.py`,
`control_plane_load_profile.py` and others) store a `ping_success` flag from a
`"0% packet loss"` substring match, which also matches 100% loss; raw packet
counts were not kept. The flag cannot show delivery.

## F. Regeneration check (2026-10-02)

The package was extracted from commit state into a clean directory and
`paper1_analysis.py`, `stage2_full_compare_analysis.py`,
`stage2_full_compare_paired_analysis.py` and
`control_plane_load_profile_analysis.py` were run there. All four statistics
JSON files and all eight `results/paper1/*.png` figures were reproduced
byte-for-byte after the paired JSON was refreshed to include the added fields
(before the refresh the paired JSON differed only by those added keys; no
existing value differed).
