#!/usr/bin/env python3
"""Read-only source/cleanup check on the Linux lab after campaign completion."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def run(argv):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
    return dict(argv=argv,rc=p.returncode,stdout=p.stdout,stderr=p.stderr)


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--campaign',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if not (a.campaign/'completed.json').exists():raise RuntimeError('Collection has not completed')
    source=json.loads((a.campaign/'amendment_02.json').read_text())['source_sha256']
    actual={name:hashlib.sha256((a.root/name).read_bytes()).hexdigest() for name in source}
    mismatches=[name for name in source if actual[name]!=source[name]]
    services={}
    for short in ('daim','osken','onos','odl'):
        unit=f'daim-review-{short}.service'
        services[unit]=run(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','MainPID','-p','Result'])
    bridges=run(['ovs-vsctl','list-br'])
    rows=[json.loads(l) for f in a.campaign.glob('block*/attempts.jsonl') for l in f.read_text().splitlines()]
    owned={name for r in rows for name in r.get('bridge_map',{}).values()}
    residual=sorted(owned.intersection(bridges['stdout'].splitlines()))
    ledger=a.root/'results/identity_sequence.txt'
    out=dict(wall_ns=time.time_ns(),source_basis='amendment_02.json',source_sha256=actual,
             source_mismatches=mismatches,services=services,ovs_bridges=bridges,
             remaining_scheduled_experimental_bridges=residual,
             controller_listener=run(['ss','-lntp','sport = :6653']),
             identity_ledger=ledger.read_text() if ledger.exists() else None,
             scope='Post-collection snapshot. No service, interface, source, or raw measurement is changed by this check.')
    with a.out.open('x') as f:json.dump(out,f,indent=2)
    if mismatches or residual or bridges['rc']:raise RuntimeError('Final source/bridge check needs review; details retained')
    for unit,result in services.items():
        fields=dict(l.split('=',1) for l in result['stdout'].splitlines() if '=' in l)
        if result['rc'] or fields.get('MainPID')!='0' or fields.get('ActiveState') not in ('inactive','failed'):
            raise RuntimeError('Experimental service still running or status unreadable: '+unit)
    print(json.dumps(dict(source_files_verified=len(source),services_stopped=len(services),remaining_experimental_bridges=residual)))


if __name__=='__main__':main()
