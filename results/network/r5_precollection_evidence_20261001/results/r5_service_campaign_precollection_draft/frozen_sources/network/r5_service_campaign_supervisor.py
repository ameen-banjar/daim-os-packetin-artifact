#!/usr/bin/env python3
"""Freeze then execute a bounded, randomized service campaign on the lab VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import time
import gzip
import shutil
from r5_service_campaign import CONDITIONS

PLATFORMS={
    'daim_process_per_rule':'daim', 'reactive_osken':'osken',
    'onos_native_fwd':'onos', 'odl_native_l2switch':'odl',
}
APPLICATION_LOGS={
    'onos_native_fwd':'/home/ubuntu/onos-spike/onos-2.7.0/apache-karaf-4.2.9/data/log/karaf.log',
    'odl_native_l2switch':'/home/ubuntu/odl-spike/karaf-0.24.0/data/log/karaf.log',
}

def run(argv,timeout=60):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    return dict(argv=argv,rc=p.returncode,stdout=p.stdout,stderr=p.stderr)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--execute',action='store_true')
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    runner=Path(__file__).with_name('r5_service_campaign.py')
    tracked=[runner,Path(__file__),runner.with_name('s56_measurement.py'),
        runner.with_name('daim_bridge_controller.py'),runner.with_name('daim_core_bridge.py'),
        runner.with_name('r5_daim_service_controller.py'),
        runner.with_name('r5_osken_service_controller.py'),
        runner.with_name('osken_reactive_baseline_controller.py'),
        root/'analysis/r5_service_campaign_analysis.py',root/'implementation/build/libdaim_core.so']
    tracked += [root/name for name in ('service_manifest.json','native_bundle_manifest.json','active_bundle_verification.json','environment_snapshot.json') if (root/name).exists()]
    tracked += [f for f in (root/'implementation').rglob('*') if f.is_file() and 'build' not in f.relative_to(root/'implementation').parts and (f.suffix in ('.c','.h') or f.name=='Makefile')]
    hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in tracked}
    if not args.execute:
        args.out.mkdir(exist_ok=False,parents=True)
        schedule=[];rng=random.Random(20261043)
        for block in range(1,6):
            order=list(PLATFORMS);rng.shuffle(order)
            schedule.extend(dict(block=block,platform=name,unit='daim-review-'+PLATFORMS[name]+'.service') for name in order)
        plan=dict(schedule=schedule,source_sha256=hashes,seed_platform_order=20261043,
            seed_condition_order=20261001,planned_attempts=340,
            conditions='12 switch-count/concurrent-pair combinations plus 5 fault scenarios',
            platform_sessions=20,session_listener_timeout_s=180,session_settle_s=30,
            inference='Exploratory run-level descriptive distributions; no architecture ranking, no maximum-throughput claim',
            faults='link restore, software switch restart, host move, controlled controller restart, SIGKILL then externally initiated restart',
            exclusions='No silent replacement; software execution errors pause collection; service failures are retained',
            physical_scope='Single VM OVS domains, not physical switches or distributed controller clusters',
            resources='Controller service cgroup including children; OVS and probe harness excluded and VM resources recorded separately',
            cold_service_metric='Concurrent first ICMP probes between fresh endpoint pairs; includes ARP and native application policy',
            recovery='30 seconds from restoration initiation to observed successful probe completion; not automatic failover',
            startup='Each platform is restarted at each block, followed by fixed 30 seconds after listener opens; each topology has fixed 10 seconds after connection')
        plan['conditions_list']=CONDITIONS
        plan['switch_restoration']='OVS bridge recreated and its trial-specific management socket group access restored before recovery probing; no manual forwarding rules added'
        plan['health_readiness']='Then up to 20 seconds of health-pair probe initiations, all attempts retained; cold measurement runs even if health readiness fails'
        plan['statistics']='Run-level descriptive mean/median/range; nominal exact Clopper-Pearson success intervals conditional on stated eligibility, independent-run/constant-probability assumption; no inferential platform ranking'
        (args.out/'frozen_plan.json').write_text(json.dumps(plan,indent=2))
        for f in tracked:
            dest=args.out/'frozen_sources'/f.relative_to(root)
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        print(json.dumps(plan,indent=2));return
    plan=json.loads((args.out/'frozen_plan.json').read_text())
    if hashes!=plan['source_sha256']: raise RuntimeError('Frozen source changed')
    if (args.out/'execution_started.json').exists(): raise RuntimeError('Refusing duplicate collection')
    (args.out/'execution_started.json').write_text(json.dumps(dict(epoch=time.time(),source_sha256=hashes)))
    with (args.out/'sessions.jsonl').open('x') as log:
        for i,spec in enumerate(plan['schedule']):
            session=args.out/f"block{spec['block']:02d}_{spec['platform']}"
            started=time.time();event=dict(spec=spec,started_epoch=started)
            for short in PLATFORMS.values():
                result=run(['systemctl','stop','daim-review-'+short+'.service'])
                if result['rc']: raise RuntimeError(str(result))
            follower=None;application_log=None
            if spec['platform'] in APPLICATION_LOGS:
                application_log=args.out/(session.name+'.application.log')
                stream=application_log.open('xb')
                follower=subprocess.Popen(['tail','-n','0','-F',APPLICATION_LOGS[spec['platform']]],stdout=stream,stderr=subprocess.STDOUT)
            event['start']=run(['systemctl','start',spec['unit']])
            deadline=time.monotonic()+180;ready=False
            while time.monotonic()<deadline:
                try:
                    with socket.create_connection(('127.0.0.1',6653),timeout=1): pass
                    ready=True;break
                except OSError: time.sleep(1)
            event['listener_ready']=ready
            if ready: time.sleep(30)
            with (args.out/(session.name+'.console.log')).open('x') as console:
                proc=subprocess.run([sys.executable,str(runner),'--platform',spec['platform'],
                    '--unit',spec['unit'],'--phase','bounded','--block',str(spec['block']),
                    '--out',str(session)],stdout=console,stderr=subprocess.STDOUT)
            if follower:
                follower.terminate();follower.wait(timeout=5);stream.close()
                with application_log.open('rb') as src,gzip.open(str(application_log)+'.gz','wb') as dst:shutil.copyfileobj(src,dst)
                application_log.unlink()  # lossless compressed copy is retained
            event['runner_rc']=proc.returncode
            journal=run(['journalctl','-u',spec['unit'],'--since','@'+str(int(started)),
                         '--no-pager','-o','short-iso'],timeout=30)
            (args.out/(session.name+'.journal.log')).write_text(journal['stdout']+journal['stderr'])
            event['ended_epoch']=time.time()
            log.write(json.dumps(event)+'\n');log.flush();os.fsync(log.fileno())
            print(json.dumps(event),flush=True)
            if proc.returncode: raise RuntimeError('Collection paused after instrument error')
    for short in PLATFORMS.values(): run(['systemctl','stop','daim-review-'+short+'.service'])
    (args.out/'completed.json').write_text(json.dumps(dict(epoch=time.time(),sessions=20)))

if __name__=='__main__': main()
