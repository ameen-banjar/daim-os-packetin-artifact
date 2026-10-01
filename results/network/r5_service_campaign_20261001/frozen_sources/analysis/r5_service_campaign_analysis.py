#!/usr/bin/env python3
"""Run-level descriptive analysis; retain failed and incomplete attempts."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import math

def exact_binomial_interval(x,n,alpha=.05):
    if not n:return None
    def tail(p,lower):
        indices=range(x,n+1) if lower else range(0,x+1)
        return sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in indices)
    def solve(lower):
        a,b=0.,1.
        for _ in range(70):
            m=(a+b)/2;v=tail(m,lower)
            if (v<alpha/2)==lower:a=m
            else:b=m
        return (a+b)/2
    return [0. if x==0 else solve(True),1. if x==n else solve(False)]

def describe(values):
    values=[v for v in values if v is not None]
    if not values:return {'n':0}
    return dict(n=len(values),mean=statistics.mean(values),median=statistics.median(values),min=min(values),max=max(values))

def systemd(snapshot):
    return dict(line.split('=',1) for line in snapshot.get('systemd',{}).get('stdout','').splitlines() if '=' in line)

def cpu_delta(row):
    a=systemd(row.get('workload_resources_before',{}));b=systemd(row.get('workload_resources_after',{}))
    if not a.get('InvocationID') or a.get('InvocationID')!=b.get('InvocationID'):return None
    try:
        delta=int(b['CPUUsageNSec'])-int(a['CPUUsageNSec'])
        return delta/1e9 if delta>=0 else None
    except (KeyError,ValueError):return None

def memory_after(row):
    try:return int(systemd(row['workload_resources_after'])['MemoryCurrent'])/1048576
    except (KeyError,ValueError):return None

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    plan=json.loads((args.root/'frozen_plan.json').read_text())
    groups=defaultdict(list);files={};rows=[]
    for path in sorted(args.root.glob('block*/attempts.jsonl')):
        files[str(path.relative_to(args.root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text().splitlines():
            row=json.loads(line);rows.append(row);s=row['spec']
            groups[(row['platform'],s['scenario'],s['switches'],s['flows'])].append(row)
    seen=[(r['platform'],r['spec']['scenario'],r['spec']['switches'],r['spec']['flows'],r['spec']['repetition']) for r in rows]
    if len(seen)!=len(set(seen)):raise ValueError('Duplicate scheduled condition')
    expected={(s['platform'],c['scenario'],c['switches'],c['flows'],s['block']) for s in plan['schedule'] for c in plan['conditions_list']}
    if not set(seen)<=expected:raise ValueError('Unscheduled condition')
    if (args.root/'completed.json').exists() and set(seen)!=expected:raise ValueError('Completed campaign has missing scheduled attempts')
    ids=[r['trial_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Reused trial identity')
    for field in ('ip','mac'):
        identities=[h[field] for r in rows for h in r.get('host_identities',[])]
        if len(identities)!=len(set(identities)):raise ValueError('Reused host '+field)
    dpids=[d for r in rows for d in r.get('bridge_map',{})]
    if len(dpids)!=len(set(dpids)):raise ValueError('Reused DPID')
    output=dict(planned_attempts=plan['planned_attempts'],recorded_attempts=len(rows),
        collection_complete=(args.root/'completed.json').exists(),raw_sha256=files,
        inference='Run-level exploratory descriptive results; no pooled-packet inferential tests or platform/architecture superiority claims',
        metric='External cold-endpoint service including ARP and native app policy; not pure rule-installation latency',
        limitations=['n=5 per condition; native applications differ','controller cgroup excludes OVS and harness',
                     'memory is current snapshot, not trial peak','fault recovery requires successful pre-fault baseline',
                     'no automatic failover, distributed consistency or physical switches',
                     'nominal 95% Clopper-Pearson intervals assume independent run-level Bernoulli trials with constant probability; unadjusted for multiple conditions'],groups=[])
    for key,rs in sorted(groups.items()):
        complete=[r for r in rs if r['status']=='completed']
        eligible=[r for r in complete if r.get('fault_baseline_valid') and r.get('fault_injection_verified',True) and r.get('recovery_observation_performed')]
        recovered=[r for r in eligible if r.get('recovered')]
        g=dict(platform=key[0],scenario=key[1],switches=key[2],concurrent_pairs=key[3],
            scheduled_n=5,recorded_n=len(rs),status=dict(Counter(r['status'] for r in rs)),
            cold_eligible_runs_n=len(complete),cold_eligibility='completed run with valid probe execution; connection/readiness outcomes retained separately',
            warmup_success_n=sum(r.get('warmup_all_succeeded',False) for r in complete),
            whole_cold_batch_success_n=sum(r.get('successful_probe_n')==key[3] for r in complete),
            valid_probe_total=sum(r.get('valid_probe_n',0) for r in complete),
            successful_probe_total=sum(r.get('successful_probe_n',0) for r in complete),
            run_cold_success_fraction=describe([r.get('successful_probe_n',0)/key[3] for r in complete]),
            cold_batch_wall_s_all_completed=describe([r.get('batch_s') for r in complete]),
            cgroup_cpu_s_workload_bracket=describe([cpu_delta(r) for r in complete]),
            cgroup_current_memory_mib_after_workload=describe([memory_after(r) for r in complete]))
        g['whole_cold_batch_success_nominal_95ci']=exact_binomial_interval(g['whole_cold_batch_success_n'],len(complete))
        if key[1]!='scale':
            g.update(recovery_eligible_n=len(eligible),recovered_within_30s_n=len(recovered),
                recovery_not_observed_within_30s_n=len(eligible)-len(recovered),
                recovery_observed_s_success_conditional=describe([r['recovery_observed_s'] for r in recovered]),
                recovery_ineligible_n=len(complete)-len(eligible),
                failed_baseline_n=sum(not r.get('fault_baseline_valid') for r in complete),
                no_recovery_observation_n=sum(not r.get('recovery_observation_performed') for r in complete))
            g['recovery_success_nominal_95ci']=exact_binomial_interval(len(recovered),len(eligible))
        output['groups'].append(g)
    with args.out.open('x') as f:json.dump(output,f,indent=2)
    print(json.dumps(dict(recorded=len(rows),groups=len(groups),complete=output['collection_complete'])))

if __name__=='__main__':main()
