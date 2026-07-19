#!/usr/bin/env python3
import csv, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/"results/network/stage2_baseline_raw.csv").open()))
def pct(v,q):
    v=sorted(v); r=(len(v)-1)*q; lo=int(r); hi=min(len(v)-1,lo+1); return v[lo]+(v[hi]-v[lo])*(r-lo)
out=[]
for mode in sorted({r['mode'] for r in rows}):
  for n in sorted({int(r['network_size']) for r in rows}):
    g=[r for r in rows if r['mode']==mode and int(r['network_size'])==n]; v=[float(r['install_mean_us']) for r in g]
    out.append({'evidence_level':'measured_emulation','mode':mode,'network_size':n,'n':len(g),'ping_success':sum(int(r['ping_success']) for r in g),'mean_us':statistics.fmean(v),'p50_us':pct(v,.5),'p95_us':pct(v,.95),'p99_us':pct(v,.99),'mean_sum_us':statistics.fmean(float(r['install_sum_us']) for r in g)})
with (ROOT/"results/network/stage2_baseline_summary.csv").open('w',newline='') as h:
 w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('wrote stage2_baseline_summary.csv')

