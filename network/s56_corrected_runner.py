#!/usr/bin/env python3
"""Corrected §5.6: isolated functional verification or frozen 30-block collection.

All new results use a new exclusive output directory. No legacy CSV is written.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import socket
import subprocess
import time
import uuid

from s56_measurement import PARAMETERS, dump_once, expected_rule, has_rule, preflight, ping_result, identity_matches

HERE = Path(__file__).resolve().parent
MODES = ['process_per_rule', 'persistent', 'reactive_osken']
SCENARIOS = ['warmup_only','wrong_identity','normal','unexpected_rule','ping_failure','observer_timeout','observer_error']
MAC = {i: '02:56:00:00:00:%02x' % i for i in (1, 2, 3)}
IP = {i: '10.56.0.%d' % i for i in (1, 2, 3)}

def events(path):
    result = []
    if path.exists():
        for line in path.read_text(errors='replace').splitlines():
            try:
                v = json.loads(line)
                if isinstance(v, dict) and 'event' in v:
                    result.append(v)
            except ValueError:
                pass
    return result

def wait_event(path, name, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        es = events(path)
        if any(e['event'] == 'adapter_error' for e in es):
            raise RuntimeError(str(es))
        found = [e for e in es if e['event'] == name]
        if found:
            return found[-1]
        time.sleep(0.02)
    return None

def command(argv, timeout=5):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(repr((argv, p.returncode, p.stderr)))
    return p.stdout

def control(path, trial_id, cmd):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(path)
        s.sendall(json.dumps(dict(command=cmd, trial_id=trial_id)).encode())
        data = b''
        while not data.endswith(b'\n'):
            data += s.recv(65536)
        return json.loads(data)

def ping(host, dest, count=1, ident=None):
    argv = ['ping', '-n', '-c', str(count), '-W', str(PARAMETERS['ping_wait_s'])]
    if ident is not None:
        argv += ['-e', str(ident)]
    argv.append(dest)
    p = host.popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start = time.perf_counter_ns()
    try:
        out, err = p.communicate(timeout=count * (PARAMETERS['ping_wait_s'] + 1) + 2)
        r = ping_result(out, err, p.returncode, count)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        r = dict(valid=False, success=False, stdout=out, stderr=err, error='ping_process_timeout')
    r.update(start_ns=start, end_ns=time.perf_counter_ns())
    return r

def resource_snapshot():
    return {p: Path(p).read_text() for p in ('/proc/stat','/proc/meminfo','/proc/loadavg','/proc/vmstat')}

def trial(mode, trial_num, block, outdir, dpid_base, scenario='normal'):
    from mininet.net import Mininet
    from mininet.node import OVSSwitch
    from mininet.link import TCLink
    net, proc, loghandle = None, None, None
    token = uuid.uuid4().hex[:8]
    trial_id = f'{outdir.name}-{trial_num}-{mode}-{token}'
    bridge = 's' + token  # leaves room for '-ethN' within Linux IFNAMSIZ=16
    control_path = '/tmp/s56-' + token + '.sock'
    logpath = outdir / (trial_id + '.controller.log')
    num = dpid_base + trial_num
    expected = dict(trial_id=trial_id, bridge=bridge, dpid=num, in_port=1,
        src_mac=MAC[1], dst_mac=MAC[2], src_ip=IP[1], dst_ip=IP[2],
        eth_type=2048, ip_proto=1, icmp_type=8, icmp_id=20000+trial_num, icmp_seq=1)
    config = dict(mode=mode, identity=expected, bridge=bridge, persistent_port=18655,
                  control_socket=control_path, out_port=2,
                  library=str(HERE.parent/'implementation/build-s56/libdaim_core.so'))
    if scenario == 'observer_error': config['observer_bridge'] = 's56absent'
    if scenario == 'observer_timeout': config['observer_out_port'] = 3
    r = dict(trial_id=trial_id, trial_num=trial_num, block=block, mode=mode, scenario=scenario,
             expected_identity=expected, protocol='met', target_event='not_attempted',
             connectivity='not_attempted', rule_observation='not_attempted',
             eligible_timing=False, stopped_at_phase='setup',
             before_resources=resource_snapshot())
    try:
        net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, build=False)
        sw = net.addSwitch(bridge, dpid='%016x' % num, protocols='OpenFlow13', failMode='secure')
        hosts = {}
        for i in (1,2,3):
            hosts[i] = net.addHost('h%d'%i, ip=IP[i]+'/24', mac=MAC[i])
            net.addLink(hosts[i], sw, port2=i)
        net.build()
        for h in hosts.values():
            h.cmd('sysctl -qw net.ipv6.conf.all.disable_ipv6=1')
        net.start()
        command(['ovs-vsctl','set','bridge',bridge,'other-config:disable-in-band=true'])
        # These entries generate no Ethernet traffic and no DAIM learning event.
        r['neighbor_commands'] = []
        for a,b in ((1,2),(2,1)):
            cmd = ['ip','neigh','replace',IP[b],'lladdr',MAC[b],'dev',str(hosts[a].defaultIntf()),'nud','permanent']
            out, stderr, rc = hosts[a].pexec(cmd)
            r['neighbor_commands'].append(dict(command=cmd, stdout=out, stderr=stderr, rc=rc))
            if rc:
                raise RuntimeError('neighbor setup failed')
        r['neighbors'] = {str(i): hosts[i].cmd('ip neigh show') for i in (1,2)}
        if not all(MAC[b] in r['neighbors'][str(a)] and 'PERMANENT' in r['neighbors'][str(a)] for a,b in ((1,2),(2,1))):
            raise RuntimeError('neighbor verification failed')
        env = dict(os.environ, S56_CONFIG=json.dumps(config), PYTHONUNBUFFERED='1')
        env.pop('DAIM_TARGET_IP',None)
        loghandle = logpath.open('x')
        proc = subprocess.Popen(['osken-manager',str(HERE/'s56_corrected_controller.py'),
            '--ofp-tcp-listen-port','18653'], stdout=loghandle, stderr=subprocess.STDOUT,
            env=env, start_new_session=True)
        targets = ['tcp:127.0.0.1:18653']
        if mode == 'persistent':
            targets.append('tcp:127.0.0.1:18655')
        command(['ovs-vsctl','set-controller',bridge,*targets])
        r['stopped_at_phase'] = 'controller_readiness'
        r['ready'] = wait_event(logpath,'ready',PARAMETERS['ready_s'])
        if not r['ready']:
            r['reason'] = 'readiness_timeout'
            return r
        r['stopped_at_phase'] = 'warmup'
        r['warmup_ping'] = ping(hosts[3], IP[2], 2)
        warm = [expected_rule(2,MAC[3],3),expected_rule(3,MAC[2],2)]
        r['warmup_polls'] = []
        deadline = time.monotonic()+PARAMETERS['warmup_s']
        while time.monotonic()<deadline:
            snap = dump_once(bridge)
            r['warmup_polls'].append(snap)
            if snap.get('error'):
                r['reason']='warmup_observer_error'
                return r
            if all(has_rule(snap['rules'],w) for w in warm):
                break
            time.sleep(0.05)
        else:
            r['reason']='warmup_rules_timeout'
            return r
        if not r['warmup_ping']['valid'] or not r['warmup_ping']['success']:
            r['reason']='warmup_ping_not_successful'
            return r
        time.sleep(PARAMETERS['warmup_quiet_s'])
        if scenario=='unexpected_rule':
            command(['ovs-ofctl','-O','OpenFlow13','add-flow',bridge,'priority=50,actions=normal'])
        r['preflight'] = dump_once(bridge)
        if r['preflight'].get('error') or not preflight(r['preflight']['rules'],warm):
            r.update(protocol='setup_deviation',reason='preflight_rejected')
            r['verification_pass'] = scenario=='unexpected_rule' and not r['preflight'].get('error')
            return r
        r['pre_arm'] = control(control_path, trial_id, 'status')
        if r['pre_arm']['accepted'] or any(e['event']=='timing' for e in events(logpath)):
            r.update(protocol='setup_deviation',reason='premature_capture')
            return r
        if scenario == 'warmup_only':
            r['verification_pass'] = True
            r['stopped_at_phase']='verification_complete'
            return r
        r['arm_ack'] = control(control_path,trial_id,'arm')
        if not r['arm_ack']['ok'] or not r['arm_ack']['armed']:
            raise RuntimeError('arm acknowledgement failed')
        if scenario=='ping_failure':
            net.configLinkStatus('h2',bridge,'down')
        r['stopped_at_phase'] = 'target'
        r['target_ping'] = ping(hosts[1], IP[2], 1,
             ident=expected['icmp_id']+(1 if scenario=='wrong_identity' else 0))
        r['connectivity'] = ('succeeded' if r['target_ping']['success'] else 'failed') if r['target_ping']['valid'] else 'could_not_assess'
        timing = wait_event(logpath,'timing',PARAMETERS['confirm_s']+1)
        r['timing'] = timing
        records = [e for e in events(logpath) if e['event']=='timing']
        r['timing_record_count'] = len(records)
        r['target_event'] = 'not_observed' if timing is None else ('observed' if identity_matches(timing['identity'],expected) else 'wrong_identity')
        if timing:
            r['rule_observation']=timing['observation']['status']
            ts=timing['timestamps']
            end=timing['observation']['confirmed_ns']
            ordered = [ts['t_dispatch_enter_ns']]
            if mode!='reactive_osken':
                ordered += [ts[k] for k in ('t_pre_ctypes_ns','c_entry_ns','c_decision_done_ns','c_table_write_done_ns','c_install_done_ns','c_exit_ns','t_post_ctypes_ns')]
            ordered += [ts['t_packetout_sent_ns']]
            if end is not None:
                ordered.append(end)
            r['timestamp_order_valid'] = ordered == sorted(ordered)
            r['eligible_timing'] = (r['protocol']=='met' and r['target_event']=='observed'
                and r['rule_observation']=='confirmed' and len(records)==1 and r['timestamp_order_valid'])
            if r['eligible_timing']:
                r['latency_ns']=end-ts['t_dispatch_enter_ns']
        if scenario=='wrong_identity':
            r['verification_pass']=len(records)==0
        elif scenario=='ping_failure':
            r['verification_pass']=r['connectivity']=='failed' and r['rule_observation']=='confirmed' and r['target_event']=='observed'
        elif scenario in ('observer_error','observer_timeout'):
            r['verification_pass']=r['target_event']=='observed' and r['rule_observation']==('tool_error' if scenario=='observer_error' else 'timed_out') and not r['eligible_timing']
        else:
            r['verification_pass']=r['eligible_timing'] and r['connectivity']=='succeeded'
            if block==0 and r['verification_pass']:
                r['duplicate_ping']=ping(hosts[1],IP[2],1,ident=expected['icmp_id'])
                time.sleep(0.1)
                r['records_after_duplicate']=len([e for e in events(logpath) if e['event']=='timing'])
                r['verification_pass'] &= r['records_after_duplicate']==1
        r['stopped_at_phase']='complete'
    except Exception as exc:
        r.update(protocol='execution_error',exception=repr(exc))
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
        if loghandle: loghandle.close()
        if net: net.stop()
        Path(control_path).unlink(missing_ok=True)
        r['controller_log']=str(logpath)
        r['after_resources']=resource_snapshot()
    return r

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['verify','official'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--verification-dir',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise SystemExit('Mininet requires root')
    from mininet.log import setLogLevel
    setLogLevel('warning')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (HERE/'s56_corrected_runner.py',HERE/'s56_corrected_controller.py',HERE/'s56_measurement.py',HERE/'daim_core_bridge.py',HERE/'test_s56_measurement.py')}
    lib=HERE.parent/'implementation/build-s56/libdaim_core.so'
    hashes['libdaim_core.so']=hashlib.sha256(lib.read_bytes()).hexdigest()
    if args.phase=='official':
        if args.verification_dir is None:
            raise SystemExit('official phase requires --verification-dir')
        prior=json.loads((args.verification_dir/'frozen_parameters.json').read_text())
        checks=[json.loads(l) for l in (args.verification_dir/'attempts.jsonl').read_text().splitlines()]
        if prior['hashes']!=hashes or len(checks)!=len(SCENARIOS)*len(MODES) or not all(r.get('verification_pass') for r in checks):
            raise SystemExit('verification gate failed or code changed since verification')
    subprocess.run([os.sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_s56_measurement.py'],check=True)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'frozen_parameters.json').write_text(json.dumps(dict(parameters=PARAMETERS,hashes=hashes,
        phase=args.phase,clock=time.get_clock_info('perf_counter').__dict__,
        uname=list(os.uname())),indent=2))
    rng=random.Random(PARAMETERS['seed'])
    schedule=[]
    if args.phase=='official':
        for block in range(1,31):
            modes=list(MODES);rng.shuffle(modes)
            schedule.extend(dict(block=block,mode=m,scenario='normal') for m in modes)
    else:
        schedule=[dict(block=0,mode=m,scenario=s) for s in SCENARIOS for m in MODES]
    (args.out/'schedule.json').write_text(json.dumps(schedule,indent=2))
    dpid_base=int(uuid.uuid4().hex[:10],16)*1000
    with (args.out/'attempts.jsonl').open('x') as f:
        for n,item in enumerate(schedule,1):
            r=trial(trial_num=n,outdir=args.out,dpid_base=dpid_base,**item)
            f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            print(json.dumps({k:r.get(k) for k in ('trial_num','block','mode','scenario','protocol','target_event','connectivity','rule_observation','eligible_timing','verification_pass','reason','exception','latency_ns')}),flush=True)
            if args.phase=='verify' and r.get('protocol')=='execution_error':
                break

if __name__=='__main__':
    main()
