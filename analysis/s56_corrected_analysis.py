#!/usr/bin/env python3
"""Frozen-before-official-collection estimates for corrected §5.6.

Conditional paired estimates use common valid blocks; all attempts remain in
outcome denominators. Percentile bootstrap intervals are marginal, not
family-wise superiority tests. Tail quantiles are descriptive only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from s56_measurement import identity_matches, expected_rule, has_rule, PARAMETERS

def interval(values, statistic, seed):
    if not values:
        return None
    a=np.asarray(values,dtype=float)
    rng=np.random.default_rng(seed)
    samples=a[rng.integers(0,len(a),size=(PARAMETERS['bootstrap'],len(a)))]
    estimates=np.mean(samples,axis=1) if statistic=='mean' else np.median(samples,axis=1)
    return [float(v) for v in np.quantile(estimates,[0.025,0.975])]

def valid(row):
    t=row.get('timing')
    if not t or row.get('protocol')!='met' or row.get('timing_record_count')!=1:
        return False
    if not identity_matches(t['identity'],row['expected_identity']):
        return False
    obs=t['observation']
    if obs['status']!='confirmed' or not obs['polls']:
        return False
    if any(p.get('error') for p in obs['polls']):
        return False
    target=expected_rule(t['identity']['in_port'],t['identity']['dst_mac'],2)
    if not has_rule(obs['polls'][-1]['rules'],target):
        return False
    ts=t['timestamps']
    total=obs['confirmed_ns']-ts['t_dispatch_enter_ns']
    return total>=0 and row.get('timestamp_order_valid') and total==row.get('latency_ns')

def stages(row):
    t=row['timing'];s=t['timestamps'];end=t['observation']['confirmed_ns']
    if row['mode']=='reactive_osken':
        return None
    vals={
        'dispatch':s['t_pre_ctypes_ns']-s['t_dispatch_enter_ns'],
        'interop':s['c_entry_ns']-s['t_pre_ctypes_ns']+s['t_post_ctypes_ns']-s['c_exit_ns'],
        'core_decision':s['c_decision_done_ns']-s['c_entry_ns'],
        'table_write':s['c_table_write_done_ns']-s['c_decision_done_ns'],
        'adapter_call':s['c_install_done_ns']-s['c_table_write_done_ns'],
        'c_exit_tail':s['c_exit_ns']-s['c_install_done_ns'],
        'post_call_and_packetout':s['t_packetout_sent_ns']-s['t_post_ctypes_ns'],
        'confirmation_wait':end-s['t_packetout_sent_ns']}
    assert min(vals.values())>=0 and sum(vals.values())==row['latency_ns']
    return vals

def analyse(folder):
    rows=[json.loads(l) for l in (folder/'attempts.jsonl').read_text().splitlines()]
    if any(r['block']==0 or r['scenario']!='normal' for r in rows):
        raise ValueError('diagnostic attempts cannot enter official analysis')
    schedule=json.loads((folder/'schedule.json').read_text())
    assert len(rows)==len(schedule)==90
    assert [(r['block'],r['mode']) for r in rows]==[(r['block'],r['mode']) for r in schedule]
    out=dict(attempts=len(rows),seed=PARAMETERS['seed'],bootstrap_samples=PARAMETERS['bootstrap'],
        interval='95% percentile; marginal not multiplicity-adjusted',
        metric='handler entry to completion of first read confirming full target rule',
        inference='latency estimates conditional on valid confirmed measurements; no timeout imputation',
        modes={},paired={})
    groups={}
    for mode in ['process_per_rule','persistent','reactive_osken']:
        allrows=[r for r in rows if r['mode']==mode]
        good=[r for r in allrows if valid(r)]
        groups[mode]={r['block']:r['latency_ns']/1e6 for r in good}
        values=list(groups[mode].values())
        summary=dict(scheduled=len(allrows),valid_confirmed_n=len(good),
            connectivity=dict(Counter(r['connectivity'] for r in allrows)),
            rule_observation=dict(Counter(r['rule_observation'] for r in allrows)),
            protocol=dict(Counter(r['protocol'] for r in allrows)))
        if values:
            summary.update(mean_ms=float(np.mean(values)),median_ms=float(np.median(values)),
                p95_ms=float(np.quantile(values,.95)),p99_ms=float(np.quantile(values,.99)),
                min_ms=min(values),max_ms=max(values),
                mean_ci_ms=interval(values,'mean',PARAMETERS['seed']),
                median_ci_ms=interval(values,'median',PARAMETERS['seed']))
            if mode!='reactive_osken':
                pieces=[stages(r) for r in good]
                means={k:float(np.mean([p[k] for p in pieces]))/1e6 for k in pieces[0]}
                summary['stage_means_ms']=means
                summary['stage_percent_of_mean_total']={k:100*v/summary['mean_ms'] for k,v in means.items()}
                summary['integer_stage_sum_mismatches']=0
        out['modes'][mode]=summary
    for a,b in [('persistent','process_per_rule'),('persistent','reactive_osken'),('process_per_rule','reactive_osken')]:
        blocks=sorted(groups[a].keys() & groups[b].keys())
        d=[groups[a][k]-groups[b][k] for k in blocks]
        out['paired'][a+' minus '+b]=dict(common_valid_blocks=blocks,n=len(d),
            mean_difference_ms=float(np.mean(d)) if d else None,
            median_difference_ms=float(np.median(d)) if d else None,
            mean_ci_ms=interval(d,'mean',PARAMETERS['seed']),
            median_ci_ms=interval(d,'median',PARAMETERS['seed']))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=analyse(args.folder)
    with args.output.open('x') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
