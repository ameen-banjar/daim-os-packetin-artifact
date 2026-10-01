#!/usr/bin/env python3
"""Render the frozen descriptive analysis without changing any estimand."""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = {
    'daim_process_per_rule': 'DAIM process-per-rule',
    'reactive_osken': 'Reactive Os-Ken',
    'onos_native_fwd': 'ONOS native fwd',
    'odl_native_l2switch': 'OpenDaylight native L2Switch',
}


def number(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('statistics', type=Path)
    p.add_argument('--outage', type=Path, required=True)
    p.add_argument('--host', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    s = json.loads(a.statistics.read_text())
    outage = json.loads(a.outage.read_text())
    host = json.loads(a.host.read_text())
    if outage['raw_sha256'] != s['raw_sha256']:
        raise ValueError('Supplementary outage interpretation uses different raw files')
    if not s['collection_complete']:
        raise ValueError('Refusing a final report for incomplete collection')
    groups = {(g['platform'], g['scenario'], g['switches'], g['concurrent_pairs']): g
              for g in s['groups']}
    lines = [
        '# Additional controller service results', '',
        f"The fixed schedule contains {s['planned_attempts']} attempts; {s['recorded_attempts']} were recorded. "
        'This report describes application/configuration behaviour in one emulated host environment. '
        'It does not rank controller architectures or estimate maximum sustainable throughput.', '',
        'The original collector was amended after attempt eight, which failed during setup. '
        'That record remains an instrumentation error and was not replaced. The first resume '
        'failed a metadata check before starting any new trial. The amendments, original and '
        'updated sources, and every attempted schedule slot are retained.', '',
        '## Attempt accounting', '',
        '| Platform | Scheduled | Recorded | Completed workload | Health-ready completed runs | Setup or execution error | Connection timeout | Not listening |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for platform, name in NAMES.items():
        gs = [g for g in s['groups'] if g['platform'] == platform]
        count = lambda status: sum(g['status'].get(status, 0) for g in gs)
        lines.append(f"| {name} | 85 | {sum(g['recorded_n'] for g in gs)} | {count('completed')} | "
                     f"{sum(g['warmup_success_n'] for g in gs)} | {count('execution_error')} | "
                     f"{count('controller_connection_timeout')} | {count('platform_not_listening')} |")
    lines += ['', 'Completion is an instrumentation status, not a statement that packets were delivered or service recovered. '
              'Health readiness is the separate bounded health-pair check; its failure does not remove a completed workload.', '',
              '## Concurrent new endpoint pairs', '',
              'Each cell is the number of runs in which all target probes succeeded divided by completed runs. '
              'Five runs were scheduled per cell. Health-readiness failures remain in this denominator when the measured batch ran. '
              'Raw successful/valid probe totals and nominal exact intervals are in the statistics JSON.', '',
              '| Switches | New pairs | DAIM | Os-Ken | ONOS | OpenDaylight |',
              '| ---: | ---: | ---: | ---: | ---: | ---: |']
    for n in (1, 4, 8, 16):
        for k in (1, 8, 32):
            cells=[]
            for platform in NAMES:
                g=groups[(platform, 'scale', n, k)]
                cells.append(f"{g['whole_cold_batch_success_n']}/{g['cold_eligible_runs_n']}")
            lines.append(f'| {n} | {k} | '+ ' | '.join(cells)+' |')
    lines += ['', 'The workload includes ARP and native forwarding-policy behaviour. When pairs are fewer than switches, '
              'some switches carry only health-check traffic. The topology consists of separate L2 domains sharing a controller.', '',
              '## Service observed after disruption and restoration actions', '',
              'Post-action observation is eligible only after a successful pre-fault baseline, verified injection where required, '
              'and an actual observation attempt. A successful response must finish within the 30-second window. '
              'Conditional times omit non-successes; counts remain visible. Restart is externally initiated, not automatic failover. '
              'These frozen-analysis counts alone do not establish recovery from an observed outage: a native application may '
              'continue serving the new destination while its controller is stopped. The supplementary outage interpretation '
              'separates those cases using the retained downtime probes. Host movement has no probe during the detach/attach gap.', '',
              '| Platform | Event | Recorded | Eligible | Service observed within 30 s | No service observed within 30 s | Ineligible completed | Median post-action observation in s among successes |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for platform,name in NAMES.items():
        for scenario in ('link_restore','switch_restart','host_move','controller_restart','controller_crash'):
            g=groups[(platform, scenario, 1, 1)]
            med=g['recovery_observed_s_success_conditional'].get('median')
            lines.append(f"| {name} | {scenario} | {g['recorded_n']} | {g['recovery_eligible_n']} | "
                         f"{g['recovered_within_30s_n']} | {g['recovery_not_observed_within_30s_n']} | "
                         f"{g['recovery_ineligible_n']} | {number(med)} |")
    lines += ['', '## Controller service during downtime', '',
              'This supplementary interpretation was specified during collection after a completed ODL case showed '
              'successful communication to the new destination while its controller service was stopped. It changes '
              'neither the raw data nor the frozen post-action success counts. Recovery after observed loss is a narrower '
              'subset; successful downtime probes represent reachability at those probe times, not proof of continuous service.', '',
              '| Platform | Event | Eligible | Existing destination works during stop | New destination works during stop | New-destination probe loss observed | Service restored within 30 s after observed loss |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for g in outage['groups']:
        if g['scenario'] in ('controller_restart','controller_crash'):
            lines.append(f"| {NAMES[g['platform']]} | {g['scenario']} | {g['post_action_eligible_n']} | "
                         f"{g['existing_service_during_controller_stop_n']} | {g['new_destination_service_during_controller_stop_n']} | "
                         f"{g['observed_probe_loss_n']} | {g['restored_within_30s_after_observed_probe_loss_n']} |")
    lines += ['', '## Batch duration and controller resources', '',
              'Medians below are across completed runs, including runs with packet loss. Batch duration is wall time for '
              'all concurrent probe tasks, not an average per-flow installation time. CPU includes controller subprocess children '
              'but excludes OVS and the probe harness; current memory is an after-batch snapshot, not a per-trial peak. '
              'Measurements from short batches should not be interpreted as stable utilization rates. '
              'Read resource use alongside delivered-service counts: low CPU use in a failed batch is not evidence '
              'of greater efficiency, and native application/runtime footprints differ.', '',
              '| Platform | Switches | Pairs | Runs | Median batch in ms | CPU observations | Median CPU seconds | Memory observations | Median current memory in MiB |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for platform,name in NAMES.items():
        for n in (1,4,8,16):
            for k in (1,8,32):
                g=groups[(platform,'scale',n,k)]
                batch=g['cold_batch_wall_s_all_completed'].get('median')
                cpu=g['cgroup_cpu_s_workload_bracket'];mem=g['cgroup_current_memory_mib_after_workload']
                lines.append(f"| {name} | {n} | {k} | {g['cold_eligible_runs_n']} | "
                             f"{number(batch*1000 if batch is not None else None)} | {cpu['n']} | "
                             f"{number(cpu.get('median'),6)} | {mem['n']} | {number(mem.get('median'),2)} |")
    idle=host['cpu_idle_percent_second_top_sample'];swap=host['swap_page_count_delta']
    lines += ['', '## Physical-host resource context', '',
              f"The host monitor retained {host['samples']} samples with {len(host['errors'])} command/parse errors. "
              f"Interval CPU idle ranged from {idle['min']:.2f}% to {idle['max']:.2f}% "
              f"(median {idle['median']:.2f}%). Memory-pressure code counts were `{host['pressure_code_counts']}`. "
              f"Swap counters increased by {swap['Swapins']:,} input pages and {swap['Swapouts']:,} output pages; "
              f"the recorded page sizes were {host['vm_stat_page_sizes_bytes']} bytes.", '',
              'Memory pressure and host swapping were therefore present during the overall monitoring window, '
              'which also includes pauses and diagnostics. These host-wide counters cannot allocate swapping '
              'to a particular controller or prove the cause of a failed or slow trial. The timing and service '
              'observations describe this constrained environment; they do not establish isolated controller costs '
              'or production reliability. No completed attempt was discarded based on these later summaries.', '',
              '## Interpretation limits', '',
              'There are five scheduled runs per platform/condition, shared controller sessions within blocks, native '
              'application differences, and a documented collector amendment. Nominal exact intervals do not remove these '
              'limitations or establish independence; no multiplicity-adjusted platform ranking is attempted. Failures '
              'describe the tested configuration. A causal explanation requires a separately controlled investigation.', '',
              'This campaign does not establish distributed state consistency, automatic standby failover, behaviour on '
              'physical switches, or production-scale performance. Three unrelated pre-existing OVS bridges remained in the VM; '
              'host monitoring provides context rather than proof of an isolated host.', '',
              '## Provenance', '',
              f"Statistics source: `{a.statistics.name}`. SHA-256: `{hashlib.sha256(a.statistics.read_bytes()).hexdigest()}`.", '',
              f"Supplementary outage interpretation: `{a.outage.name}`. SHA-256: `{hashlib.sha256(a.outage.read_bytes()).hexdigest()}`.", '',
              f"Host context: `{a.host.name}`. SHA-256: `{hashlib.sha256(a.host.read_bytes()).hexdigest()}`.", '',
              'The statistics JSON contains hashes of every raw attempt file. The frozen plan, source snapshots, amendments, '
              'per-session application logs, flow dumps, identities and raw ping outputs remain in the corresponding data directory.', '']
    with a.out.open('x') as f:
        f.write('\n'.join(lines))
    print(a.out)


if __name__ == '__main__':
    main()
