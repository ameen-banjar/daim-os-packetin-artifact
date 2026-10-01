# Corrected Packet In experiment

This local release candidate includes a new 90-attempt Section 5.6 sample. The earlier `packetin_latency_breakdown_raw.csv` remains a historical record: its capture predicate and retained fields cannot establish the claimed h1 packet identity, and its ping success flag used an unsafe substring check. Do not pool that sample with the corrected sample or present its old figures as validated corrected results.

The corrected sample is in `results/network/s56_corrected_official_20261001/`. Its 30 randomized blocks contain one attempt per mode. All 90 attempts met the protocol and confirmed the full target rule; all 90 target pings succeeded under packet-count and exit-status checks. The identity and warm-up/arming checks, raw controller logs, every observation poll, raw ping outputs and resource snapshots are retained.

## Reanalyse the retained data

From this package root, with Python 3 and NumPy installed:

```sh
python3 network/test_s56_measurement.py
python3 analysis/s56_corrected_analysis.py results/network/s56_corrected_official_20261001 --output /tmp/s56_reproduced.json
cmp /tmp/s56_reproduced.json results/network/s56_corrected_official_20261001/statistics.json
```

Choose an unused output filename: the analyser deliberately refuses to overwrite results. The five local parser/matcher tests passed, and reanalysis from this artifact copy produced byte-identical statistics on 1 October 2026. This is an author-side package check, not independent reproduction by another research group.

## Repeat collection on an isolated Linux lab

Collection needs Mininet, OVS with OpenFlow 1.3, Linux iproute2/iputils with explicit ICMP identifiers, and an Os-Ken Python environment available to the root-run driver. No VM experiment is launched by the analysis commands above.

Build the unchanged single-Core library in its separate output directory:

```sh
make -C implementation BUILD=build-s56 build-s56/libdaim_core.so
```

The driver invokes `osken-manager` from PATH and uses TCP ports 18653/18655. Run it under a Python environment that can import Mininet, with the correct Os-Ken executable on its inherited PATH. First run all 21 functional gates, then use their directory to authorize collection with exactly the same source and library hashes:

```sh
sudo -E python3 network/s56_corrected_runner.py --phase verify --out /tmp/s56_verify_new
sudo -E python3 network/s56_corrected_runner.py --phase official --verification-dir /tmp/s56_verify_new --out /tmp/s56_official_new
```

Both output directories must be new. PATH configuration is installation-specific; verify which Python and `osken-manager` sudo will execute before collection. The saved library hash is architecture/build-specific: a fresh rebuild may differ from the recorded binary, but verification and subsequent collection on that machine must match one another. The frozen parameter record identifies the actual recorded Linux kernel, architecture and monotonic clock.

## Interpretation

The metric is handler entry to completion of the first read confirming the full target rule. It includes application execution, dispatch and observation cost; it is neither pure OVS internal installation time nor end-user response time. The eight DAIM intervals sum exactly in integer nanoseconds in all 60 DAIM trials.

Mean times were 17.268 ms for process-per-rule, 4.114 ms for persistent, and 3.877 ms for reactive Os-Ken. The paired persistent-minus-Os-Ken mean difference was 0.237 ms, with a marginal 95% bootstrap interval from -0.213 to 0.696 ms. This sample supports neither a persistent-DAIM superiority claim nor an equivalence claim relative to Os-Ken. Tail quantiles are descriptive at n=30 per mode.

The new sample uses corrected instrumentation and a later run session. Differences from historical values cannot be attributed solely to the old identity defect. The full protocol is `network/S56_PACKETIN_LATENCY_CORRECTED_PROTOCOL.md`; the original project-path hash record is `results/network/s56_freeze_20261001.json`. Those path prefixes describe the source repository layout, while the package places network/analysis files directly under its root.

This addition is local and unpublished. It is not present in the previously published v1.1.0 DOI snapshot. Publication/version/DOI and final manuscript integration remain separate steps.
