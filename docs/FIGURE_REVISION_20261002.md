# Visual-only figure revision (2026-10-02)

Three figures were redrawn because labels and legends overlapped axes or data
in the rendered manuscript. **No data, statistic or plotted value changed.**
The redrawn figures read the same statistics JSON files (`paper1_statistics.json`,
`stage2_full_compare_paired_statistics.json`), which are unmodified.

| Figure | File | Change |
| --- | --- | --- |
| 2 | `results/paper1/paper1_architecture.png` | Component boxes widened so labels fit inside them |
| 7 | `results/paper1/paper1_installation_time.png` | Legend moved off the data lines |
| 9 | `results/paper1/stage2_full_compare_paired.png` | Redrawn with matplotlib: non-overlapping legends, labelled axes, panel B in ms with tick marks (previously unlabelled ticks, label in us) |

Previous SHA-256 values of the packaged figures (the published v1.1.0 snapshot
is unchanged and keeps its own versions):

| File | Previous SHA-256 |
| --- | --- |
| paper1_architecture.png | 9ff74fe28d02e36e742e9a6e7b61c6db11a0b0abab63f0b43ed1a531927abd08 |
| paper1_installation_time.png | 6ce8a80bb3c9dc9fb2d693d352246a3e74071e961ecacd1c9aa04f536d00dda7 |
| stage2_full_compare_paired.png | 3c67ceb502f17e6016fbce5a1a70a1fc4496988ee68b2a74603b81edf2832374 |

The packaged `analysis/stage2_full_compare_paired_analysis.py` previously drew a
different colour scheme from the manuscript's Figure 9; the package now uses the
same script as the manuscript. The earlier manifest is retained as
`docs/manifest_before_figure_revision_20261002.sha256`. Not published.
