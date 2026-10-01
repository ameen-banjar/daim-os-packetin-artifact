#!/usr/bin/env python3
"""Descriptive count figures; never infer a controller-architecture ranking."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r5_service_campaign_report import NAMES


def save(fig, root, stem):
    for ext in ('png', 'svg'):
        fig.savefig(root/f'{stem}.{ext}', dpi=220)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('statistics',type=Path)
    p.add_argument('--outage',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();s=json.loads(a.statistics.read_text());o=json.loads(a.outage.read_text())
    if not s['collection_complete'] or s['raw_sha256']!=o['raw_sha256']:
        raise ValueError('Completed, matching raw samples required')
    a.out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.size':9,'svg.hashsalt':'r5-service-20261001'})
    cmap=plt.colormaps['Blues'].copy();cmap.set_bad('#dddddd')
    groups={(g['platform'],g['scenario'],g['switches'],g['concurrent_pairs']):g for g in s['groups']}
    fig,axes=plt.subplots(2,2,figsize=(9.3,7.5))
    for ax,(platform,name) in zip(axes.flat,NAMES.items()):
        values=np.full((4,3),np.nan);counts={}
        for i,n in enumerate((1,4,8,16)):
            for j,k in enumerate((1,8,32)):
                g=groups[(platform,'scale',n,k)];yes=g['whole_cold_batch_success_n'];total=g['cold_eligible_runs_n']
                if total:values[i,j]=yes/total
                counts[(i,j)]=(yes,total)
        ax.imshow(values,vmin=0,vmax=1,cmap=cmap,aspect='auto')
        for (i,j),(yes,total) in counts.items():
            ax.text(j,i,f'{yes}/{total}',ha='center',va='center',fontsize=11,
                    color='white' if total and yes/total>.65 else 'black')
        ax.set(title=name,xticks=range(3),xticklabels=[1,8,32],yticks=range(4),yticklabels=[1,4,8,16],
               xlabel='Concurrent new endpoint pairs',ylabel='Switches')
    fig.suptitle('Cold-service batches: successful runs / completed runs',fontsize=13,y=.98)
    fig.text(.055,.025,'Five runs scheduled per cell; setup errors are retained separately from completed-run denominators.\n'
             'Success requires every target probe in that batch to succeed. Native applications differ; no architecture ranking.\n'
             'Single VM on a host with recorded memory pressure and swapping; see the resource-context report.',fontsize=8)
    fig.tight_layout(rect=(0,.09,1,.96))
    save(fig,a.out,'r5_cold_service_counts')

    scenarios=['link_restore','switch_restart','host_move','controller_restart','controller_crash']
    labels=['Link\nrestored','OVS bridge\nrecreated','Host\nmoved','Controlled\nstop/start','SIGKILL +\nexternal restart']
    og={(g['platform'],g['scenario']):g for g in o['groups']}
    values=np.full((4,5),np.nan);counts={}
    for i,platform in enumerate(NAMES):
        for j,scenario in enumerate(scenarios):
            g=og[(platform,scenario)];yes=g['restored_within_30s_after_observed_probe_loss_n'];total=g['observed_probe_loss_n']
            if total:values[i,j]=yes/total
            counts[(i,j)]=(yes,total)
    fig,ax=plt.subplots(figsize=(10,4.8));ax.imshow(values,vmin=0,vmax=1,cmap=cmap,aspect='auto')
    for (i,j),(yes,total) in counts.items():
        ax.text(j,i,f'{yes}/{total}' if total else '—',ha='center',va='center',fontsize=11,
                color='white' if total and yes/total>.65 else 'black')
    ax.set(xticks=range(5),xticklabels=labels,yticks=range(4),yticklabels=list(NAMES.values()))
    plt.setp(ax.get_xticklabels(),ha='center')
    ax.set_title('Service restored within 30 s / eligible runs with observed probe loss',pad=15)
    fig.text(.05,.025,'Supplementary interpretation specified during collection. Five attempts scheduled per cell.\n'
             'Failed baselines and cases without observed probe loss are reported separately, not treated as recovery failures.\n'
             'Host movement has no probe during detach/attach. Restart is externally initiated; this is not automatic failover.\n'
             'The host experienced memory pressure and swapping; causes of individual failures were not isolated.',fontsize=8)
    fig.tight_layout(rect=(0,.16,1,1))
    save(fig,a.out,'r5_observed_loss_restoration_counts')
    (a.out/'figure_notes.json').write_text(json.dumps(dict(
        scale_denominator='Completed runs with valid probe execution; retain the one setup error separately',
        fault_denominator='Successful pre-fault baseline, eligible observation and demonstrated probe loss',
        color='Fraction within the printed denominator; five scheduled runs per cell, no inferential ranking',
        raw_sha256=s['raw_sha256']),indent=2))
    print(a.out)


if __name__=='__main__':main()
