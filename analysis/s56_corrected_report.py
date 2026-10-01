#!/usr/bin/env python3
"""Render corrected-sample results without replacing historical manuscript data."""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = {'process_per_rule': 'DAIM process-per-rule', 'persistent': 'DAIM persistent',
         'reactive_osken': 'Reactive Os-Ken'}
STAGES = {
    'dispatch': 'Handler entry to bridge-call start',
    'interop': 'Python–C entry and return intervals (including conversions/possible lock wait)',
    'core_decision': 'C entry to decision timestamp',
    'table_write': 'Decision to table-write timestamp',
    'adapter_call': 'OVS adapter-call interval',
    'c_exit_tail': 'C installation-call completion to C exit timestamp',
    'post_call_and_packetout': 'C return to PacketOut submission return',
    'confirmation_wait': 'PacketOut submission return to full-rule observation',
}


def interval(values):
    return '['+', '.join(f'{v:.3f}' for v in values)+']'


def main():
    p=argparse.ArgumentParser();p.add_argument('statistics',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    s=json.loads(a.statistics.read_text())
    lines=['# Corrected Section 5.6 results', '',
        f"The fixed schedule contained {s['attempts']} attempts in 30 randomized blocks, with one attempt per mode per block. "
        'These are new observations from the corrected instrument, not a repaired or pooled version of the historical sample.', '',
        '## Outcomes and measured intervals', '',
        'The endpoint is completion of the first read confirming the full target rule. The start is entry of the '
        'identity-matched packet into the application handler. Values below include application, dispatch, '
        'observation-tool and scheduling time; they are not pure OVS installation time or end-user latency.', '',
        '| Mode | Scheduled | Valid and rule-confirmed | Successful target ping | Mean ms | 95% mean CI | Median ms | p95 ms | p99 ms |',
        '| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |']
    for mode,name in NAMES.items():
        m=s['modes'][mode]
        lines.append(f"| {name} | {m['scheduled']} | {m['valid_confirmed_n']} | {m['connectivity'].get('succeeded',0)} | "
                     f"{m['mean_ms']:.3f} | {interval(m['mean_ci_ms'])} | {m['median_ms']:.3f} | {m['p95_ms']:.3f} | {m['p99_ms']:.3f} |")
    lines+=['', f"Intervals use {s['bootstrap_samples']:,} bootstrap samples, seed {s['seed']}; {s['interval']}. "
             'Tail quantiles are descriptive at 30 observations per mode.', '',
             '## Paired block differences', '',
             '| A minus B | Common valid blocks | Mean difference ms | 95% CI | Median of paired differences ms | 95% CI |',
             '| --- | ---: | ---: | --- | ---: | --- |']
    for label,d in s['paired'].items():
        left,right=label.split(' minus ')
        lines.append(f"| {NAMES[left]} minus {NAMES[right]} | {d['n']} | {d['mean_difference_ms']:.3f} | "
                     f"{interval(d['mean_ci_ms'])} | {d['median_difference_ms']:.3f} | {interval(d['median_ci_ms'])} |")
    lines+=['', 'The persistent-minus-Os-Ken interval includes zero. This sample does not support a claim of '
             'persistent DAIM superiority relative to Os-Ken, and it does not establish statistical equivalence. '
             'The median of paired differences is not the difference of the two marginal medians.', '',
             '## DAIM stage decomposition', '',
             '| Interval | Process-per-rule mean ms | Share of mean total % | Persistent mean ms | Share of mean total % |',
             '| --- | ---: | ---: | ---: | ---: |']
    for key,name in STAGES.items():
        x=s['modes']['process_per_rule'];y=s['modes']['persistent']
        lines.append(f"| {name} | {x['stage_means_ms'][key]:.6f} | {x['stage_percent_of_mean_total'][key]:.4f} | "
                     f"{y['stage_means_ms'][key]:.6f} | {y['stage_percent_of_mean_total'][key]:.4f} |")
    mismatch=sum(s['modes'][m]['integer_stage_sum_mismatches'] for m in ('process_per_rule','persistent'))
    lines+=['', f'Integer-nanosecond stage-sum mismatches: {mismatch}. The eight intervals exhaust the total before rounding.', '',
             'The adapter-call interval is not isolated process-creation cost. The Python–C intervals are not pure '
             'ctypes overhead. PacketOut timestamps follow the application submission call, not an observed wire transmission. '
             'The confirmation interval does not experimentally separate OVS work from tool and scheduling effects.', '',
             '## Scope and provenance', '',
             'The corrected protocol uses full packet identity, explicit activation after verified warm-up, pre-flight '
             'rule absence, complete rule-field matching, and raw ping counts plus exit-status checks. The historical '
             'sample remains unchanged and cannot retrospectively establish those properties. Session and instrument '
             'changes preclude attributing old/new numerical differences solely to the identity defect.', '',
             'This report is a standalone evidence document. It does not automatically update the manuscript, response '
             'letter, submission PDF or published DOI release.', '',
             f"Statistics: `{a.statistics.name}`; SHA-256 `{hashlib.sha256(a.statistics.read_bytes()).hexdigest()}`.", '']
    with a.out.open('x') as f:f.write('\n'.join(lines))
    print(a.out)


if __name__=='__main__':main()
