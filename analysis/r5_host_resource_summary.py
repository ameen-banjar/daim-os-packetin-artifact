#!/usr/bin/env python3
"""Summarize retained host samples without claiming resource isolation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics


def describe(values):
    return dict(n=len(values),min=min(values),median=statistics.median(values),max=max(values)) if values else dict(n=0)


def main():
    p=argparse.ArgumentParser();p.add_argument('raw',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=[json.loads(x) for x in a.raw.read_text().splitlines()]
    errors=[];pressure=Counter();idle=[];swap=[];page_sizes=set()
    for i,r in enumerate(rows):
        s=r['samples']
        for name,v in s.items():
            if v.get('rc')!=0:errors.append(dict(sample=i,command=name,error=v))
        if s['pressure'].get('rc')==0:pressure[s['pressure']['stdout'].strip()]+=1
        text=s['cpu_memory'].get('stdout','')
        samples=re.findall(r'CPU usage:.*?([\d.]+)% idle',text)
        if s['cpu_memory'].get('rc')==0 and len(samples)>=2:
            # top's second sample is the measured interval; do not report its
            # first observation as an equivalent interval sample.
            idle.append(float(samples[-1]))
        else:errors.append(dict(sample=i,command='cpu_interval_parse',matches=len(samples)))
        vm=s['vm_stat'].get('stdout','')
        page=re.search(r'page size of (\d+) bytes',vm)
        if page:page_sizes.add(int(page.group(1)))
        entry={}
        for name in ('Swapins','Swapouts'):
            found=re.search(r'^'+name+r':\s*(\d+)\.',vm,re.M)
            if found:entry[name]=int(found.group(1))
        if s['vm_stat'].get('rc')==0 and len(entry)==2:swap.append(entry)
        else:errors.append(dict(sample=i,command='vm_stat_swap_parse',fields=list(entry)))
    gaps=[(b['wall_time_ns']-a['wall_time_ns'])/1e9 for a,b in zip(rows,rows[1:])]
    monotonic=all(b[k]>=a[k] for a,b in zip(swap,swap[1:]) for k in ('Swapins','Swapouts'))
    delta={k:swap[-1][k]-swap[0][k] for k in ('Swapins','Swapouts')} if swap and monotonic else None
    out=dict(samples=len(rows),raw_sha256=hashlib.sha256(a.raw.read_bytes()).hexdigest(),
             first_wall_ns=rows[0]['wall_time_ns'] if rows else None,last_wall_ns=rows[-1]['wall_time_ns'] if rows else None,
             sample_gap_s=describe(gaps),cpu_idle_percent_second_top_sample=describe(idle),
             pressure_code_counts=dict(pressure),vm_stat_page_sizes_bytes=sorted(page_sizes),
             swap_counter_samples=len(swap),swap_counters_nondecreasing=monotonic,swap_page_count_delta=delta,
             errors=errors,interpretation='Whole-window host context, not VM-only usage or proof of isolation. No causal allocation of host load to individual controllers.')
    with a.out.open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(samples=len(rows),errors=len(errors),cpu_idle=out['cpu_idle_percent_second_top_sample'],pressure=dict(pressure))))


if __name__=='__main__':main()
