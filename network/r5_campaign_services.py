#!/usr/bin/env python3
"""Create isolated, resource-accounted service units on the existing lab VM.

Does not change system Java, published code, controller databases, or enable
services at boot. Native controller application differences remain explicit.
"""
from pathlib import Path
import subprocess
import json
import hashlib

BASE=Path('/home/ubuntu/review_campaign')
ONOS=Path('/home/ubuntu/onos-spike/onos-2.7.0/apache-karaf-4.2.9')
ODL=Path('/home/ubuntu/odl-spike/karaf-0.24.0')
LEGACY='/home/ubuntu/onos-spike/jdk11-legacy/jdk-11.0.16+8'

def main():
    BASE.mkdir(exist_ok=True)
    backup=BASE/'disabled_timing_targets'
    backup.mkdir(exist_ok=True)
    for name in ('fwd_timing_target.txt','fwd_timing_target_mac.txt','odl_timing_target.txt'):
        p=Path('/tmp')/name
        if p.exists():
            dest=backup/name
            if dest.exists():
                raise RuntimeError('refusing to overwrite timing target backup')
            p.rename(dest)
    units={
        'daim':(BASE,f'/home/ubuntu/daim_venv/bin/osken-manager {BASE}/network/r5_daim_service_controller.py --ofp-tcp-listen-port 6653',
                ['DAIM_ADAPTER_MODE=process_per_rule',f'DAIM_BRIDGE_MAP={BASE}/bridge_map.json']),
        'osken':(BASE,f'/home/ubuntu/daim_venv/bin/osken-manager {BASE}/network/r5_osken_service_controller.py --ofp-tcp-listen-port 6653',[f'DAIM_BRIDGE_MAP={BASE}/bridge_map.json']),
        'onos':(ONOS,f'{ONOS}/bin/karaf server',[f'JAVA_HOME={LEGACY}','JAVA_MIN_MEM=256M','JAVA_MAX_MEM=1536M']),
        'odl':(ODL,f'{ODL}/bin/karaf server',['JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64','JAVA_MIN_MEM=256M','JAVA_MAX_MEM=1536M']),
    }
    manifest={}
    for platform,(cwd,command,env) in units.items():
        name='daim-review-'+platform+'.service'
        content='[Unit]\nDescription=DAIM review isolated '+platform+'\nAfter=network.target openvswitch-switch.service\n[Service]\nType=simple\nUser=ubuntu\nWorkingDirectory='+str(cwd)+'\n'
        env=['PATH=/home/ubuntu/daim_venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',*env]
        content+=''.join('Environment="'+e+'"\n' for e in env)
        content+='ExecStart='+command+'\nCPUAccounting=yes\nMemoryAccounting=yes\nMemoryMax=2500M\nTasksMax=4096\nTimeoutStopSec=20\nKillMode=control-group\nRestart=no\n'
        target=Path('/run/systemd/system')/name
        if target.exists() and target.read_text()!=content:
            raise RuntimeError('refusing to replace different service '+str(target))
        target.write_text(content)
        (BASE/name).write_text(content)
        manifest[name]=dict(sha256=hashlib.sha256(content.encode()).hexdigest(),content=content)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    (BASE/'service_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Installed four isolated units; none started or enabled.')

if __name__=='__main__':main()
