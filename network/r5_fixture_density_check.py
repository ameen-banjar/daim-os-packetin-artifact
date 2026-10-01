#!/usr/bin/env python3
"""Isolated diagnostic for dense OVS startup, outside the official schedule."""
import argparse
import json
from pathlib import Path
import shlex
import mininet.node
from mininet.log import setLogLevel
import r5_service_campaign as campaign

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--pipe',action='store_true');a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);calls=[];base=mininet.node.OVSSwitch
    class TracedSwitch(base):
        def vsctl(self,*args,**kwargs):
            command=' '.join(str(x) for x in args)
            if a.pipe:
                r=campaign.cmd(['ovs-vsctl',*shlex.split(command)],timeout=20)
                calls.append(dict(command_characters=len(command),**r))
                if r['rc']:raise RuntimeError(str(r))
                return r['stdout']+r['stderr']
            value=super().vsctl(*args,**kwargs)
            calls.append(dict(command_characters=len(command),command=command,pty_output=value))
            return value
    mininet.node.OVSSwitch=TracedSwitch
    config=argparse.Namespace(platform='reactive_osken_diagnostic',unit='daim-review-fixturecheck.service',port=17653,settle=10,recovery_window=30,out=a.out)
    setLogLevel('warning')
    result=campaign.run_trial(config,dict(scenario='scale',switches=1,flows=32,repetition=0))
    result['startup_calls']=calls;result['diagnostic_only']=True
    (a.out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result.get(k) for k in ('status','error','successful_probe_n','observed_forwarding_rules')}))
    print(json.dumps([dict(length=c['command_characters'],output=c.get('pty_output'),rc=c.get('rc')) for c in calls]))

if __name__=='__main__':main()
