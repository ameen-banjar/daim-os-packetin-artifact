#!/usr/bin/env python3
"""Standalone figures for the corrected sample; never overwrites old figures."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from s56_corrected_analysis import valid

def main():
    p=argparse.ArgumentParser();p.add_argument('sample',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    stats=json.loads((a.sample/'statistics.json').read_text())
    rows=[json.loads(l) for l in (a.sample/'attempts.jsonl').read_text().splitlines()]
    modes=['process_per_rule','persistent','reactive_osken']
    names=['DAIM\nprocess-per-rule','DAIM\npersistent','Reactive\nOs-Ken']
    colors=['#D55E00','#0072B2','#009E73']
    plt.rcParams.update({'font.size':10,'svg.hashsalt':'s56-corrected-20261001','axes.spines.top':False,'axes.spines.right':False})
    rng=np.random.default_rng(20261001)
    fig,ax=plt.subplots(figsize=(7.2,4.8))
    for i,(mode,color) in enumerate(zip(modes,colors)):
        vals=[r['latency_ns']/1e6 for r in rows if r['mode']==mode and valid(r)]
        s=stats['modes'][mode];mean=s['mean_ms'];lo,hi=s['mean_ci_ms']
        ax.scatter(i+rng.uniform(-.14,.14,len(vals)),vals,s=22,color=color,alpha=.65,zorder=3)
        ax.errorbar(i+.25,mean,yerr=[[mean-lo],[hi-mean]],fmt='D',markersize=5,color='black',capsize=5,zorder=4)
        ax.text(i,30.1,f'n = {len(vals)}',ha='center',fontsize=9)
    ax.set(xticks=range(3),xticklabels=names,ylabel='Handler entry to full-rule observation (ms)',ylim=(0,32),xlim=(-.5,2.6))
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.text(.12,.02,'Dots: individual trials. Diamonds: means with marginal 95% bootstrap intervals.\nCorrected 90-attempt sample; 30 valid confirmed trials per mode.',fontsize=8)
    fig.tight_layout(rect=(0,.10,1,1))
    for ext in ('png','svg'):fig.savefig(a.out/f's56_corrected_latency.{ext}',dpi=240)
    plt.close(fig)
    labels={
        'dispatch':'Handler entry → bridge call',
        'interop':'Python–C entry/return intervals',
        'core_decision':'C entry → decision timestamp',
        'table_write':'Decision → table-write timestamp',
        'adapter_call':'OVS adapter-call interval',
        'c_exit_tail':'C installation done → C exit',
        'post_call_and_packetout':'C return → PacketOut submission return',
        'confirmation_wait':'PacketOut submission return → rule observed'}
    palette=['#7B3294','#A6CEE3','#33A02C','#B2DF8A','#D55E00','#999999','#E69F00','#0072B2']
    fig,ax=plt.subplots(figsize=(8.4,4.5));left=np.zeros(2)
    for (key,label),color in zip(labels.items(),palette):
        vals=np.array([stats['modes'][m]['stage_means_ms'][key] for m in modes[:2]])
        ax.barh([1,0],vals,left=left,color=color,height=.5,label=label)
        left+=vals
    for y,m in zip([1,0],modes[:2]):
        s=stats['modes'][m];ax.text(s['mean_ms']+.15,y,f"{s['mean_ms']:.3f} ms",va='center',fontsize=9)
    ax.set(yticks=[1,0],yticklabels=['DAIM process-per-rule','DAIM persistent'],xlabel='Mean measured interval (ms)',xlim=(0,20),ylim=(-.6,1.6))
    ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    fig.legend(loc='lower center',bbox_to_anchor=(.5,.01),ncol=2,frameon=False,fontsize=8)
    fig.tight_layout(rect=(0,.26,1,1))
    for ext in ('png','svg'):fig.savefig(a.out/f's56_corrected_stages.{ext}',dpi=240)
    plt.close(fig)
    (a.out/'figure_notes.json').write_text(json.dumps(dict(source=str(a.sample),
        labels=labels,stage_sum='All eight intervals sum exactly before rounding in every DAIM trial',
        caveats=['Entry/return interval includes conversions and possible lock waiting',
                 'PacketOut timestamp follows the application send_msg call; it is not a wire-transmission timestamp',
                 'Confirmation interval does not isolate OVS execution from observer/tool/scheduling delays',
                 'Intervals are marginal, not multiplicity-adjusted superiority or equivalence tests',
                 'Tiny stages remain in data/plot but may not be visually resolvable']),indent=2))

if __name__=='__main__':main()
