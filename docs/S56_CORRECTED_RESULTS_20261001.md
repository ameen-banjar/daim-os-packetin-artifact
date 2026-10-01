# Corrected Section 5.6 results

The fixed schedule contained 90 attempts in 30 randomized blocks, with one attempt per mode per block. These are new observations from the corrected instrument, not a repaired or pooled version of the historical sample.

## Outcomes and measured intervals

The endpoint is completion of the first read confirming the full target rule. The start is entry of the identity-matched packet into the application handler. Values below include application, dispatch, observation-tool and scheduling time; they are not pure OVS installation time or end-user latency.

| Mode | Scheduled | Valid and rule-confirmed | Successful target ping | Mean ms | 95% mean CI | Median ms | p95 ms | p99 ms |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| DAIM process-per-rule | 30 | 30 | 30 | 17.268 | [16.162, 18.595] | 16.409 | 24.423 | 27.718 |
| DAIM persistent | 30 | 30 | 30 | 4.114 | [3.815, 4.425] | 4.134 | 5.807 | 6.058 |
| Reactive Os-Ken | 30 | 30 | 30 | 3.877 | [3.598, 4.184] | 3.703 | 5.262 | 5.944 |

Intervals use 20,000 bootstrap samples, seed 20261001; 95% percentile; marginal not multiplicity-adjusted. Tail quantiles are descriptive at 30 observations per mode.

## Paired block differences

| A minus B | Common valid blocks | Mean difference ms | 95% CI | Median of paired differences ms | 95% CI |
| --- | ---: | ---: | --- | ---: | --- |
| DAIM persistent minus DAIM process-per-rule | 30 | -13.154 | [-14.631, -11.913] | -12.215 | [-12.846, -11.342] |
| DAIM persistent minus Reactive Os-Ken | 30 | 0.237 | [-0.213, 0.696] | 0.248 | [-0.384, 0.809] |
| DAIM process-per-rule minus Reactive Os-Ken | 30 | 13.391 | [12.319, 14.671] | 12.501 | [11.833, 13.129] |

The persistent-minus-Os-Ken interval includes zero. This sample does not support a claim of persistent DAIM superiority relative to Os-Ken, and it does not establish statistical equivalence. The median of paired differences is not the difference of the two marginal medians.

## DAIM stage decomposition

| Interval | Process-per-rule mean ms | Share of mean total % | Persistent mean ms | Share of mean total % |
| --- | ---: | ---: | ---: | ---: |
| Handler entry to bridge-call start | 0.142374 | 0.8245 | 0.157771 | 3.8350 |
| Python–C entry and return intervals (including conversions/possible lock wait) | 0.060204 | 0.3486 | 0.034169 | 0.8306 |
| C entry to decision timestamp | 0.001431 | 0.0083 | 0.001186 | 0.0288 |
| Decision to table-write timestamp | 0.000610 | 0.0035 | 0.000724 | 0.0176 |
| OVS adapter-call interval | 13.690126 | 79.2817 | 0.062194 | 1.5118 |
| C installation-call completion to C exit timestamp | 0.000181 | 0.0010 | 0.000069 | 0.0017 |
| C return to PacketOut submission return | 0.075156 | 0.4352 | 0.062816 | 1.5269 |
| PacketOut submission return to full-rule observation | 3.297616 | 19.0970 | 3.795014 | 92.2476 |

Integer-nanosecond stage-sum mismatches: 0. The eight intervals exhaust the total before rounding.

The adapter-call interval is not isolated process-creation cost. The Python–C intervals are not pure ctypes overhead. PacketOut timestamps follow the application submission call, not an observed wire transmission. The confirmation interval does not experimentally separate OVS work from tool and scheduling effects.

## Scope and provenance

The corrected protocol uses full packet identity, explicit activation after verified warm-up, pre-flight rule absence, complete rule-field matching, and raw ping counts plus exit-status checks. The historical sample remains unchanged and cannot retrospectively establish those properties. Session and instrument changes preclude attributing old/new numerical differences solely to the identity defect.

This report is a standalone evidence document. It does not automatically update the manuscript, response letter, submission PDF or published DOI release.

Statistics: `statistics.json`; SHA-256 `5cb04d652d5b57b0ee799b4e9ebabaeddb26b9c5800ee44efdcfa2447c31cde8`.
