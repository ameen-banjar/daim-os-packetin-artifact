#!/usr/bin/env python3
"""Raw macOS host context; not CPU pinning or proof of isolation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--stop-file',type=Path,required=True);a=p.parse_args()
    with a.out.open('x') as f:
        while not a.stop_file.exists():
            row=dict(wall_time_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),samples={})
            for name,argv in [('vm_stat',['vm_stat']),('pressure',['sysctl','-n','kern.memorystatus_vm_pressure_level']),('swap',['sysctl','vm.swapusage']),('cpu_memory',['top','-l','2','-s','1','-n','0'])]:
                start=time.monotonic_ns()
                try:
                    r=subprocess.run(argv,capture_output=True,text=True,timeout=8)
                    value=dict(rc=r.returncode,stdout=r.stdout,stderr=r.stderr)
                except Exception as exc:value=dict(error=repr(exc))
                row['samples'][name]=dict(start_ns=start,end_ns=time.monotonic_ns(),**value)
            f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
            for _ in range(10):
                if a.stop_file.exists():break
                time.sleep(1)

if __name__=='__main__':main()
