#!/usr/bin/env python3
import json, os, signal, subprocess, time
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import LinearTopo
from mininet.log import setLogLevel
ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'results/network/real_controller_smoke.json'
APP=ROOT/'network/osken_learning_controller.py'
def ctl_state():
    out={}
    for b in ('s1','s2'):
        p=subprocess.run(['ovs-vsctl','get-controller',b],text=True,capture_output=True)
        out[b]=p.stdout.strip()
    return out
def main():
    setLogLevel('warning'); subprocess.run(['mn','-c'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ctl=subprocess.Popen(['osken-manager',str(APP),'--ofp-tcp-listen-port','6653'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    net=None; result={}
    try:
        time.sleep(2); net=Mininet(topo=LinearTopo(k=2),controller=lambda name: RemoteController(name,ip='127.0.0.1',port=6653),switch=OVSSwitch,autoSetMacs=True)
        net.start(); time.sleep(2); result['controller_pid']=ctl.pid; result['controller_state_before']=ctl_state(); h1,h2=net.hosts
        before=h1.cmd('ping -c 5 -W 1 '+h2.IP()); result['ping_before']=before
        os.kill(ctl.pid,signal.SIGTERM); ctl.wait(timeout=5); result['controller_stopped']=True; time.sleep(1)
        after=h1.cmd('ping -c 20 -i 0.05 -W 1 '+h2.IP()); result['ping_after']=after; result['controller_state_after']=ctl_state()
    finally:
        if net: net.stop()
        if ctl.poll() is None: ctl.terminate(); ctl.wait(timeout=5)
        subprocess.run(['mn','-c'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    LOG.parent.mkdir(parents=True,exist_ok=True); LOG.write_text(json.dumps(result,indent=2)+'\n'); print(LOG)
if __name__=='__main__': main()
