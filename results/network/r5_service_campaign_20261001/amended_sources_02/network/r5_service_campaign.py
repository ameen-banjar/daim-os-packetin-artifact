#!/usr/bin/env python3
"""Common external service-level probes, independent of controller language.

This is application-service evaluation, NOT a matched internal Packet-In timer.
Native application/rule differences and all readiness failures are retained.
Run one platform at a time on the same VM. Requires an already started controller.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import random
import subprocess
import time
import uuid
import re
import grp
import hashlib
import socket
import fcntl
import shlex

CONDITIONS=[dict(scenario='scale',switches=n,flows=c) for n in (1,4,8,16) for c in (1,8,32)]
CONDITIONS += [dict(scenario=s,switches=1,flows=1) for s in ('link_restore','switch_restart','host_move','controller_restart','controller_crash')]

def allocate_identity(root):
    """Durable monotonically unique IDs across diagnostics and all platforms."""
    ledger=root/'identity_sequence.txt'
    with ledger.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);f.seek(0)
        n=int(f.read() or '0')+1
        if n>=0xffffff: raise RuntimeError('identity namespace exhausted')
        f.seek(0);f.truncate();f.write(str(n));f.flush();os.fsync(f.fileno())
    return n
from s56_measurement import ping_result

def cmd(args,timeout=10):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    return dict(argv=args,rc=p.returncode,stdout=p.stdout,stderr=p.stderr)

def ping(host,ip,count=1,wait=1):
    start=time.monotonic_ns()
    p=host.popen(['ping','-n','-c',str(count),'-W',str(wait),ip],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        out,err=p.communicate(timeout=count*(wait+1)+2)
        r=ping_result(out,err,p.returncode,count)
    except subprocess.TimeoutExpired:
        p.kill();out,err=p.communicate()
        r=dict(valid=False,success=False,stdout=out,stderr=err,error='probe_timeout')
    r.update(start_ns=start,end_ns=time.monotonic_ns(),source_host=host.name,source_ip=host.IP(),destination_ip=ip,requested_count=count,response_wait_s=wait)
    m=re.search(r'(?:rtt|round-trip).*?= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)',out)
    if m: r['rtt_min_avg_max_mdev_ms']=list(map(float,m.groups()))
    return r

def resources(unit):
    start=time.monotonic_ns()
    r=dict(systemd=cmd(['systemctl','show',unit,'-p','CPUUsageNSec','-p','MemoryCurrent','-p','MemoryPeak','-p','TasksCurrent','-p','InvocationID','-p','ActiveState','-p','Result']),
        proc_stat=Path('/proc/stat').read_text(),meminfo=Path('/proc/meminfo').read_text())
    r.update(start_ns=start,end_ns=time.monotonic_ns(),memory_peak_scope='service lifetime, not per-trial peak')
    return r

def flows(switches):
    return {s.name:cmd(['ovs-ofctl','-O','OpenFlow13','dump-flows',s.name]) for s in switches}

def grant_trial_socket(s,r):
    sock=Path('/var/run/openvswitch')/(s.name+'.mgmt')
    deadline=time.monotonic()+2
    while not sock.exists() and time.monotonic()<deadline:time.sleep(.01)
    if not sock.exists():raise RuntimeError('Experimental management socket did not appear: '+str(sock))
    original=sock.stat()
    os.chown(sock,-1,grp.getgrnam('ubuntu').gr_gid)
    os.chmod(sock,original.st_mode | 0o060)
    r['events'].append(dict(event='trial_socket_group_access',socket=str(sock),original_mode=original.st_mode,original_gid=original.st_gid,at_ns=time.monotonic_ns()))

def wait_connections(switches,timeout=30):
    deadline=time.monotonic()+timeout;last={}
    while time.monotonic()<deadline:
        last={}
        for s in switches:
            ids=cmd(['ovs-vsctl','get','Bridge',s.name,'controller'])
            uuids=re.findall(r'[0-9a-f]{8}-[0-9a-f-]{27,}',ids['stdout'])
            vals=[cmd(['ovs-vsctl','get','Controller',u,'is_connected']) for u in uuids]
            last[s.name]=dict(ids=ids,connections=vals)
        if all(x['connections'] and all(v['rc']==0 and v['stdout'].strip()=='true' for v in x['connections']) for x in last.values()):
            return True,last
        time.sleep(.1)
    return False,last

def run_trial(args, spec):
    from mininet.net import Mininet
    from mininet.node import OVSSwitch,RemoteController
    serial=allocate_identity(Path(__file__).resolve().parents[1]/'results')
    token=f'{serial:06x}'
    base=0xCA00000000000000+serial*256
    net=None
    r=dict(spec=spec,platform=args.platform,trial_id=token,status='started',events=[])
    r['start_wall_ns']=time.time_ns()
    r['ovs_startup_calls']=[]
    class RecordedOVSSwitch(OVSSwitch):
        def vsctl(self,*parts,**kwargs):
            # Same per-switch OVSDB transaction, via argv/pipes rather than a
            # PTY command string; preserve exit status and both output streams.
            command=' '.join(str(x) for x in parts)
            result=cmd(['ovs-vsctl',*shlex.split(command)],timeout=20)
            r['ovs_startup_calls'].append(result)
            if result['rc']:raise RuntimeError('OVSDB startup command failed; output retained')
            return result['stdout']+result['stderr']
    r['resources_before']=resources(args.unit)
    try:
        # Between trials only: do not let a preceding restart's boot time
        # contaminate the next independent workload condition.
        start_ready=time.monotonic_ns();ready_deadline=time.monotonic()+180
        while True:
            try:
                with socket.create_connection(('127.0.0.1',args.port),timeout=1): pass
                break
            except OSError:
                if time.monotonic()>=ready_deadline:
                    r['status']='platform_not_listening';return r
                time.sleep(1)
        r['pre_trial_listener_wait']=dict(start_ns=start_ready,end_ns=time.monotonic_ns())
        net=Mininet(controller=None,switch=RecordedOVSSwitch,build=False)
        ctl=net.addController('c0',controller=RemoteController,ip='127.0.0.1',port=args.port)
        switches=[];destinations=[];primers=[];senders=[];allhosts=[];restart_destination=None
        k=0
        def host(sw,subnet,role):
            nonlocal k
            k+=1
            name='h'+str(k)
            mac='02:%02x:%02x:%02x:%02x:%02x'%((serial>>16)&255,(serial>>8)&255,serial&255,subnet,role)
            network_id=serial*16+subnet-1
            if network_id>=65536: raise RuntimeError('Unique private IPv4 namespace exhausted')
            h=net.addHost(name,ip=f'10.{network_id>>8}.{network_id&255}.{role}/24',mac=mac)
            net.addLink(h,sw)
            allhosts.append(h)
            return h
        for i in range(spec['switches']):
            sw=net.addSwitch('r'+token+str(i),dpid='%016x'%(base+i),protocols='OpenFlow13',failMode='secure')
            switches.append(sw)
            destinations.append(host(sw,i+1,1));primers.append(host(sw,i+1,2))
        for j in range(spec['flows']):
            i=j%len(switches)
            # Cold, unique endpoint PAIRS; a shared primed destination would
            # give destination-only ONOS rules a systematic warm-cache advantage.
            a=host(switches[i],i+1,3+2*(j//len(switches)))
            b=host(switches[i],i+1,4+2*(j//len(switches)))
            senders.append((a,b,switches[i]))
        if spec['scenario'] in ('controller_restart','controller_crash'):
            restart_destination=host(switches[0],1,240)
        r['bridge_map']={s.dpid:s.name for s in switches}
        mapping_path=Path(__file__).resolve().parents[1]/'bridge_map.json'
        temporary=mapping_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(r['bridge_map']));temporary.chmod(0o644)
        os.replace(temporary,mapping_path)
        net.build()
        for h in allhosts: h.cmd('sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1')
        net.start()
        r['host_identities']=[dict(name=h.name,ip=h.IP(),mac=h.MAC()) for h in allhosts]
        for s in switches:
            cmd(['ovs-vsctl','set','Bridge',s.name,'other-config:disable-in-band=true'])
            grant_trial_socket(s,r)
            if args.platform=='daim_persistent':
                if len(switches)!=1: raise ValueError('persistent adapter supports one switch only')
                cfg=cmd(['ovs-vsctl','set-controller',s.name,f'tcp:127.0.0.1:{args.port}','tcp:127.0.0.1:6655'])
                if cfg['rc']: raise RuntimeError(str(cfg))
        r['connected'],r['connection_evidence']=wait_connections(switches)
        if not r['connected']:
            r['status']='controller_connection_timeout';return r
        # Fixed stabilization window, identical for all platforms. Not timed.
        time.sleep(args.settle)
        r['pre_warm_flows']=flows(switches)
        r['warmup_history']=[];warm_deadline=time.monotonic()+20
        while True:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(primers)) as pool:
                probes=list(pool.map(lambda pair:ping(pair[0],pair[1].IP(),count=2),zip(primers,destinations)))
            r['warmup_history'].append(probes)
            r['warmup']=probes
            if any(not p.get('valid') for p in probes): raise RuntimeError('Invalid health-probe execution; raw probes retained')
            if all(p.get('valid') and p.get('success') for p in probes) or time.monotonic()>=warm_deadline: break
            time.sleep(.2)
        r['warmup_all_succeeded']=all(p.get('valid') and p.get('success') for p in r['warmup'])
        r['pre_target_flows']=flows(switches)
        # Report warm-up failure as a result; still attempt the common service
        # workload to distinguish warm-up/readiness from eventual reachability.
        r['workload_resources_before']=resources(args.unit)
        start=time.monotonic_ns()
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(senders)) as pool:
            futures=[pool.submit(ping,h,d.IP()) for h,d,_ in senders]
            r['first_flow_probes']=[f.result() for f in futures]
        end=time.monotonic_ns()
        r['batch_start_ns'],r['batch_end_ns']=start,end
        r['batch_s']=(end-start)/1e9
        r['valid_probe_n']=sum(p.get('valid',False) for p in r['first_flow_probes'])
        if r['valid_probe_n']!=len(senders): raise RuntimeError('Invalid cold-probe execution; raw probes retained')
        r['successful_probe_n']=sum(p.get('valid',False) and p.get('success',False) for p in r['first_flow_probes'])
        r['successful_probes_per_second']=r['successful_probe_n']/r['batch_s']
        r['workload_resources_after']=resources(args.unit)
        r['post_target_flows']=flows(switches)
        r['observed_forwarding_rules']={name:bool(re.search(r'actions=.*output:',x['stdout'])) for name,x in r['post_target_flows'].items() if x['rc']==0}
        if spec['scenario']!='scale':
            h,d,sw=senders[0]
            r['switch_ports_before_fault']={str(intf):port for intf,port in sw.ports.items()}
            r['fault_baseline']=ping(h,d.IP(),count=2)
            if not r['fault_baseline'].get('valid'): raise RuntimeError('Invalid pre-fault probe execution')
            r['fault_baseline_valid']=bool(r['fault_baseline'].get('valid') and r['fault_baseline'].get('success'))
            r['fault_at_ns']=time.monotonic_ns()
            if spec['scenario']=='link_restore':
                net.configLinkStatus(d.name,sw.name,'down')
                r['during_fault']=ping(h,d.IP())
                r['restore_at_ns']=time.monotonic_ns()
                net.configLinkStatus(d.name,sw.name,'up')
            elif spec['scenario']=='switch_restart':
                r['switch_stop']=cmd(['ovs-vsctl','del-br',sw.name])
                if r['switch_stop']['rc']: raise RuntimeError('Switch removal command failed')
                r['during_fault']=ping(h,d.IP())
                r['restore_at_ns']=time.monotonic_ns()
                sw.start([ctl])
                grant_trial_socket(sw,r)  # recreated socket must regain the same trial-only access
            elif spec['scenario'] in ('controller_restart','controller_crash'):
                cg=cmd(['systemctl','show',args.unit,'-p','ControlGroup','--value'])['stdout'].strip()
                cgfile=Path('/sys/fs/cgroup')/cg.lstrip('/')/'cgroup.procs'
                r['controller_cgroup_before_stop']=dict(path=str(cgfile),pids=cgfile.read_text() if cgfile.exists() else None)
                stop=(['systemctl','kill','--kill-whom=all','--signal=SIGKILL',args.unit]
                      if spec['scenario']=='controller_crash' else ['systemctl','stop',args.unit])
                r['controller_stop']=cmd(stop,timeout=60)
                stop_deadline=time.monotonic()+5
                while cgfile.exists() and cgfile.read_text().strip() and time.monotonic()<stop_deadline: time.sleep(.1)
                r['controller_cgroup_after_stop']=cgfile.read_text() if cgfile.exists() else ''
                r['fault_injection_verified']=not r['controller_cgroup_after_stop'].strip()
                if not r['fault_injection_verified']: raise RuntimeError('Controller cgroup still contains processes after requested stop')
                r['during_fault_existing_flow']=ping(h,d.IP())
                r['during_fault_new_destination']=ping(h,restart_destination.IP())
                r['restore_at_ns']=time.monotonic_ns()
                r['restart_command']=cmd(['systemctl','start',args.unit],timeout=60)
                d=restart_destination  # distinct unprimed destination; no flow clearing
            elif spec['scenario']=='host_move':
                oldip,oldmac=d.IP(),d.MAC()
                net.delLinkBetween(d,sw)
                newlink=net.addLink(d,sw,port2=100)
                d.setMAC(oldmac,intf=str(newlink.intf1));d.setIP(oldip+'/24',intf=str(newlink.intf1))
                sw.attach(newlink.intf2)
                r['restore_at_ns']=time.monotonic_ns()
                # A single standardized location announcement, retained as
                # protocol traffic. No manual flow deletion or controller fix.
                p=d.popen(['arping','-U','-c','1','-I',str(newlink.intf1),oldip],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                out,err=p.communicate(timeout=4);r['location_announcement']=dict(rc=p.returncode,stdout=out,stderr=err)
                if p.returncode: raise RuntimeError('Location announcement command failed')
            for key in ('during_fault','during_fault_existing_flow','during_fault_new_destination'):
                if key in r and not r[key].get('valid'): raise RuntimeError('Invalid downtime-probe execution')
            history=[];deadline=r['restore_at_ns']/1e9+args.recovery_window
            r['recovery_history']=history
            while time.monotonic()<deadline:
                p=ping(h,d.IP());history.append(p)
                if not p.get('valid'): raise RuntimeError('Invalid recovery-probe execution')
                if p.get('valid') and p.get('success'):break
                time.sleep(.1)
            r['recovery_history']=history
            r['recovery_observation_performed']=bool(history)
            r['recovered']=bool(history and history[-1].get('valid') and history[-1].get('success') and history[-1]['end_ns']<=int(deadline*1e9))
            r['recovery_deadline_ns']=int(deadline*1e9)
            r['last_probe_may_finish_after_deadline']=True
            r['recovery_observed_s']=(history[-1]['end_ns']-r['restore_at_ns'])/1e9 if r['recovered'] else None
            r['post_fault_flows']=flows(switches)
            r['switch_ports_after_fault']={str(intf):port for intf,port in sw.ports.items()}
        r['status']='completed'
    except Exception as exc:
        r.update(status='execution_error',error=repr(exc))
    finally:
        if net:
            try:
                net.stop()
                for controller in net.controllers: controller.terminate()
            except Exception as exc:
                r['cleanup_error']=repr(exc)
                r['status']='execution_error'
        r['resources_after']=resources(args.unit)
        r['end_wall_ns']=time.time_ns()
    return r

def main():
    os.environ['LC_ALL']='C'
    p=argparse.ArgumentParser()
    p.add_argument('--platform',required=True)
    p.add_argument('--unit',required=True)
    p.add_argument('--port',type=int,default=6653)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--phase',choices=['verify','preflight','bounded'],default='verify')
    p.add_argument('--settle',type=float,default=10)
    p.add_argument('--recovery-window',type=float,default=30)
    p.add_argument('--block',type=int,choices=range(1,6))
    p.add_argument('--case',choices=['scale','link_restore','switch_restart','host_move','controller_restart','controller_crash'])
    p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    from mininet.log import setLogLevel
    setLogLevel('warning')
    if args.resume:
        if args.phase!='bounded':raise ValueError('Resume only applies to a frozen scheduled sample')
    else:args.out.mkdir(parents=True,exist_ok=False)
    configs=list(CONDITIONS)
    if args.platform=='daim_persistent': configs=[c for c in configs if c['switches']==1 and c['scenario']!='controller_restart']
    if args.phase=='verify': configs=[dict(scenario='scale',switches=1,flows=1)]
    if args.phase=='preflight': configs=[dict(scenario='scale',switches=1,flows=1),dict(scenario='scale',switches=16,flows=32)]+[c for c in configs if c['scenario']!='scale']
    if args.case:
        if args.phase=='bounded': raise ValueError('No selective official cases allowed')
        configs=[c for c in configs if c['scenario']==args.case]
    schedule=[];rng=random.Random(20261001)
    for rep in range(1, (6 if args.phase=='bounded' else 2)):
        group=[dict(c,repetition=rep) for c in configs];rng.shuffle(group);schedule+=group
    if args.phase=='bounded' and args.block: schedule=[s for s in schedule if s['repetition']==args.block]
    existing=[]
    if args.resume:
        assert json.loads((args.out/'schedule.json').read_text())==schedule
        old=json.loads((args.out/'parameters.json').read_text())
        for key in ('platform','unit','port','phase','settle','recovery_window','block'):
            if key=='recovery_window' and isinstance(old[key],str):
                # The original metadata accidentally replaced the numeric
                # default with its description. Verify the immutable source
                # and frozen plan instead; never silently infer a new value.
                frozen=args.out.parent/'frozen_sources/network/r5_service_campaign.py'
                plan=json.loads((args.out.parent/'frozen_plan.json').read_text())
                assert hashlib.sha256(frozen.read_bytes()).hexdigest()==plan['source_sha256']['network/r5_service_campaign.py']
                assert "p.add_argument('--recovery-window',type=float,default=30)" in frozen.read_text()
                assert old[key]=='from restore initiation through first successful probe COMPLETION; late completions retained but not counted within window'
                assert args.recovery_window==30
                continue
            assert old[key]==getattr(args,key),(key,old[key],getattr(args,key))
        existing=[json.loads(x) for x in (args.out/'attempts.jsonl').read_text().splitlines()]
        assert [x['spec'] for x in existing]==schedule[:len(existing)]
        assert len(existing)<len(schedule)
    else:(args.out/'schedule.json').write_text(json.dumps(schedule,indent=2))
    params_path=args.out/('resume_parameters.json' if args.resume else 'parameters.json')
    with params_path.open('x') as params:params.write(json.dumps({**vars(args),'out':str(args.out),
        'resume_after_recorded_attempts':len(existing),'recorded_attempts_are_never_retried':True,
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('s56_measurement.py'))},
        'recovery_eligibility':'interpret recovery only when fault_baseline_valid; retain every other result separately',
        'health_readiness':'after fixed 10-second settle, retry disjoint health-pair probes within bounded 20-second initiation window; retain every probe; no trial exclusion on readiness failure',
        'recovery_window_definition':'from restore initiation through first successful probe COMPLETION; late completions retained but not counted within window',
        'unit_of_analysis':'one complete topology/workload run',
        'metric':'externally observed cold-endpoint service probes including ARP; not pure controller throughput',
        'topology':'independent L2 domains sharing one controller; concurrent probes between fresh unique endpoint pairs; disjoint health-check pair per switch',
        'startup_policy':'one controller session per platform; unique DPID and MAC identities per run',
        'inference':'bounded exploratory sample, no architectural performance ranking'},indent=2))
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (args.out/'attempts.jsonl').open('a' if args.resume else 'x') as f:
        for spec in schedule[len(existing):]:
            r=run_trial(args,spec)
            r['collector_source_sha256']=source_hash
            f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            print(json.dumps({k:r.get(k) for k in ('trial_id','platform','spec','status','warmup_all_succeeded','successful_probe_n','batch_s','recovered','error')}),flush=True)
            if r['status']=='execution_error':
                raise RuntimeError('Instrument execution error preserved; collection paused')

if __name__=='__main__':main()
