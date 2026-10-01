#!/usr/bin/env python3
"""Independent raw-record consistency checks, supplementary to frozen analysis.

Does not alter, filter or replace records. Findings must be reviewed before
interpreting affected conditions, even when the original collector completed.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))
from s56_measurement import ping_result, parse_flows


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();findings=[];rows=[];checked=Counter();mobility=[];seen_probes={}
    def issue(row, category, detail):
        findings.append(dict(trial_id=row.get('trial_id'),platform=row.get('platform'),category=category,detail=detail))
    def inspect_ping(row, obj, where):
        if isinstance(obj,dict):
            if 'requested_count' in obj and 'source_host' in obj:
                checked['probe_records_checked']+=1
                identity=(row.get('trial_id'),obj.get('start_ns'),obj.get('end_ns'),obj.get('source_ip'),obj.get('destination_ip'))
                encoded=json.dumps(obj,sort_keys=True)
                if identity not in seen_probes:
                    seen_probes[identity]=encoded;checked['unique_probe_events']+=1
                elif seen_probes[identity]!=encoded:
                    issue(row,'conflicting_duplicate_probe_record',where)
                if 'rc' not in obj:
                    issue(row,'probe_missing_return_code',where)
                else:
                    parsed=ping_result(obj.get('stdout',''),obj.get('stderr',''),obj['rc'],obj['requested_count'])
                    for key in ('valid','success','tx','rx'):
                        if parsed.get(key)!=obj.get(key):issue(row,'probe_reparse_mismatch',dict(where=where,field=key))
                    # A second count check intentionally does not call the collector's
                    # parser or use a percentage substring as a success predicate.
                    summaries=[line for line in obj.get('stdout','').splitlines()
                               if 'packets transmitted,' in line and 'received' in line]
                    try:
                        if len(summaries)!=1:raise ValueError('expected one packet-count summary')
                        fields=summaries[0].split(',')
                        tx=int(fields[0].split()[0]);rx=int(fields[1].split()[0])
                        success=(tx==rx==obj['requested_count'] and obj['rc']==0)
                        if (tx,rx,success)!=(obj.get('tx'),obj.get('rx'),obj.get('success')):
                            issue(row,'independent_count_check_mismatch',where)
                        checked['independent_count_checks']+=1
                    except (ValueError,IndexError) as exc:
                        issue(row,'independent_count_parse_error',dict(where=where,error=str(exc)))
            for key,value in obj.items():
                if isinstance(value,(dict,list)):inspect_ping(row,value,where+'/'+str(key))
        elif isinstance(obj,list):
            for i,value in enumerate(obj):inspect_ping(row,value,where+'/'+str(i))
    for path in sorted(a.root.glob('block*/attempts.jsonl')):
        lines=path.read_bytes().splitlines(keepends=True)
        rs=[json.loads(line) for line in lines];rows.extend(rs)
        schedule=json.loads((path.parent/'schedule.json').read_text())
        if [r['spec'] for r in rs]!=schedule[:len(rs)]:issue({},'schedule_order_mismatch',str(path))
        for r in rs:
            inspect_ping(r,r,'')
            if r['status']!='completed':continue
            checked['completed_runs']+=1
            ps=r['first_flow_probes']
            if len(ps)!=r['spec']['flows']:issue(r,'wrong_cold_probe_count',len(ps))
            if sum(p.get('valid',False) for p in ps)!=r['valid_probe_n']:issue(r,'valid_count_mismatch',None)
            if sum(p.get('valid',False) and p.get('success',False) for p in ps)!=r['successful_probe_n']:issue(r,'success_count_mismatch',None)
            for p in ps:
                if not r['batch_start_ns']<=p['start_ns']<=p['end_ns']<=r['batch_end_ns']:
                    issue(r,'probe_outside_batch_bracket',p['source_host'])
            for stage in ('pre_warm_flows','pre_target_flows','post_target_flows','post_fault_flows'):
                for bridge,v in r.get(stage,{}).items():
                    checked['flow_reads']+=1
                    if v['rc']!=0:issue(r,'flow_read_error',dict(stage=stage,bridge=bridge,rc=v['rc']))
            scenario=r['spec']['scenario']
            if scenario in ('controller_restart','controller_crash'):
                before=r.get('controller_cgroup_before_stop',{}).get('pids','')
                if not before or not before.strip():issue(r,'controller_not_alive_before_injection',None)
                if r.get('controller_cgroup_after_stop','').strip():issue(r,'controller_alive_after_stop',None)
                old=r['fault_baseline']['destination_ip'];new=r['during_fault_new_destination']['destination_ip']
                if old==new:issue(r,'reused_recovery_destination',old)
                if any(p['destination_ip']!=new for p in r['recovery_history']):issue(r,'wrong_recovery_destination',None)
            if scenario in ('link_restore','switch_restart') and r['fault_baseline_valid']:
                if r['during_fault'].get('success'):issue(r,'disruption_did_not_break_probe',scenario)
            if scenario=='host_move':
                if 100 not in r['switch_ports_after_fault'].values():issue(r,'destination_move_port_missing',None)
                dst=r['fault_baseline']['destination_ip']
                mac=next(h['mac'] for h in r['host_identities'] if h['ip']==dst)
                matching=[]
                for bridge,dump in r['post_fault_flows'].items():
                    if dump['rc']==0:
                        try:
                            matching.extend(dict(bridge=bridge,rule=rule) for rule in parse_flows(dump['stdout']) if rule.get('dl_dst')==mac)
                        except ValueError as exc:issue(r,'mobility_flow_parse',str(exc))
                mobility.append(dict(trial_id=r['trial_id'],platform=r['platform'],destination_mac=mac,
                    removed_ports=sorted(set(r['switch_ports_before_fault'].values())-set(r['switch_ports_after_fault'].values())),
                    added_ports=sorted(set(r['switch_ports_after_fault'].values())-set(r['switch_ports_before_fault'].values())),
                    recovered=r['recovered'],baseline_valid=r['fault_baseline_valid'],
                    post_fault_rules_explicitly_matching_destination_mac=matching))
            if scenario!='scale':
                history=r['recovery_history'];deadline=r['recovery_deadline_ns']
                expected=bool(history and history[-1].get('valid') and history[-1].get('success') and history[-1]['end_ns']<=deadline)
                if expected!=r['recovered']:issue(r,'recovery_classification_mismatch',None)
                if r['recovered']:
                    duration=(history[-1]['end_ns']-r['restore_at_ns'])/1e9
                    if duration!=r['recovery_observed_s'] or duration<0:issue(r,'recovery_duration_mismatch',duration)
    prefix_check=None
    amendment=a.root/'amendment_01.json'
    if amendment.exists():
        m=json.loads(amendment.read_text());raw=a.root/'block01_reactive_osken/attempts.jsonl'
        prefix=b''.join(raw.read_bytes().splitlines(keepends=True)[:m['original_record_count']])
        prefix_check=hashlib.sha256(prefix).hexdigest()==m['original_prefix_sha256']
        if not prefix_check:issue({},'original_prefix_changed',None)
    out=dict(recorded_attempts=len(rows),status=dict(Counter(r['status'] for r in rows)),
             checked=dict(checked),original_prefix_unchanged=prefix_check,findings=findings,
             probe_count_note='warmup also repeats the final warmup_history entry; record checks and distinct probe events are therefore reported separately',
             supplementary_mobility_flow_observations=mobility,
             mobility_scope='Post-hoc projection of rules explicitly naming the destination MAC. Not a full pipeline trace, causal isolation, or proof that a listed rule handled every packet.',
             interpretation='Post-collection consistency audit; does not infer causal correctness or change the frozen estimands')
    with a.out.open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(recorded=len(rows),checks=dict(checked),findings=len(findings))))


if __name__=='__main__':main()
