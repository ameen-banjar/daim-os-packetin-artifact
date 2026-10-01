#!/usr/bin/env python3
"""Supplement frozen post-action success counts with observed-outage evidence.

Specified during collection after inspecting the first controller-crash cases;
not a prospectively frozen analysis. No collector, schedule or raw data change.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from r5_service_campaign_analysis import describe, exact_binomial_interval


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    records=[];groups=defaultdict(list);hashes={}
    for f in sorted(a.root.glob('block*/attempts.jsonl')):
        hashes[str(f.relative_to(a.root))]=hashlib.sha256(f.read_bytes()).hexdigest()
        for line in f.read_text().splitlines():
            r=json.loads(line);scenario=r['spec']['scenario']
            if scenario=='scale':continue
            entry=dict(trial_id=r['trial_id'],platform=r['platform'],scenario=scenario,
                status=r['status'],baseline_valid=r.get('fault_baseline_valid',False),
                injection_verified=r.get('fault_injection_verified',True),
                observation_performed=r.get('recovery_observation_performed',False),
                post_action_service_within_30s=r.get('recovered',False),
                post_action_service_time_s=r.get('recovery_observed_s'),outage_observed=False)
            eligible=(entry['status']=='completed' and entry['baseline_valid'] and entry['injection_verified'] and entry['observation_performed'])
            entry['post_action_eligible']=eligible
            if not eligible:
                entry['classification']='not_eligible_for_post_action_comparison'
            else:
                if scenario in ('controller_restart','controller_crash'):
                    probe=r['during_fault_new_destination'];old=r['during_fault_existing_flow']
                    entry['existing_service_during_controller_stop']=old['success']
                    entry['new_destination_service_during_controller_stop']=probe['success']
                    assert probe['valid'] and old['valid']
                    entry['outage_observed']=not probe['success']
                    entry['outage_basis']='fresh-destination probe while controller cgroup was empty'
                elif scenario in ('link_restore','switch_restart'):
                    probe=r['during_fault'];assert probe['valid']
                    entry['outage_observed']=not probe['success']
                    entry['outage_basis']='probe while link or software bridge was down'
                elif scenario=='host_move':
                    history=r['recovery_history'];assert history
                    entry['outage_observed']=not history[0]['success']
                    entry['outage_basis']='first probe after host move; no probe during physical detach/attach gap'
                if entry['outage_observed']:
                    entry['classification']='service_observed_after_probe_loss' if entry['post_action_service_within_30s'] else 'no_service_observed_within_window_after_probe_loss'
                else:
                    entry['classification']='no_probe_loss_observed_before_post_action_success' if entry['post_action_service_within_30s'] else 'post_action_failure_without_prior_demonstrated_probe_loss'
            records.append(entry);groups[(entry['platform'],scenario)].append(entry)
    result=dict(analysis_timing='Supplementary interpretation defined during collection after a native ODL case showed new-destination connectivity while the controller was stopped',
        distinction='A successful post-action probe is not proof of recovery unless an interruption was observed. No observed probe loss does not prove uninterrupted service between probes.',
        changes_to_collection='none',raw_sha256=hashes,groups=[],records=records)
    for (platform,scenario),rs in sorted(groups.items()):
        eligible=[r for r in rs if r['post_action_eligible']]
        lost=[r for r in eligible if r['outage_observed']]
        restored=[r for r in lost if r['post_action_service_within_30s']]
        g=dict(platform=platform,scenario=scenario,recorded_n=len(rs),post_action_eligible_n=len(eligible),
            classifications=dict(Counter(r['classification'] for r in rs)),observed_probe_loss_n=len(lost),
            restored_within_30s_after_observed_probe_loss_n=len(restored),
            no_service_within_30s_after_observed_probe_loss_n=len(lost)-len(restored),
            post_action_time_s_conditional_on_observed_loss_and_service=describe([r['post_action_service_time_s'] for r in restored]),
            nominal_exact_95ci_conditional_on_observed_loss=exact_binomial_interval(len(restored),len(lost)))
        if scenario in ('controller_restart','controller_crash'):
            g['existing_service_during_controller_stop_n']=sum(r['existing_service_during_controller_stop'] for r in eligible)
            g['new_destination_service_during_controller_stop_n']=sum(r['new_destination_service_during_controller_stop'] for r in eligible)
        result['groups'].append(g)
    with a.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(disruption_records=len(records),groups=len(groups))))


if __name__=='__main__':main()
