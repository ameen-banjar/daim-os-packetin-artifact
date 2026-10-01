"""Pure measurement helpers for the corrected experiment; no Mininet dependency."""
import re
import subprocess
import time

PARAMETERS = dict(ready_s=20.0, warmup_s=5.0, confirm_s=3.0,
                  poll_sleep_s=0.0005, call_s=1.0, ping_wait_s=1,
                  warmup_quiet_s=0.2, seed=20261001, bootstrap=20000)
META = {'cookie', 'duration', 'n_packets', 'n_bytes', 'idle_age', 'hard_age'}
IDENTITY = ('trial_id', 'bridge', 'dpid', 'in_port', 'src_mac', 'dst_mac',
            'src_ip', 'dst_ip', 'eth_type', 'ip_proto', 'icmp_type', 'icmp_id', 'icmp_seq')

def parse_flows(text):
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or 'reply' in line.lower():
            continue
        if ' actions=' not in line:
            raise ValueError('unparseable flow line: ' + line)
        head, action = line.split(' actions=', 1)
        fields = {}
        for part in head.split(','):
            part = part.strip()
            if not part:
                continue
            if '=' not in part:
                fields[part] = True
            else:
                k, v = part.split('=', 1)
                if k in fields:
                    raise ValueError('duplicate field ' + k)
                fields[k] = v.lower()
        fields['actions'] = action.strip().lower()
        fields.setdefault('table', '0')
        rules.append(fields)
    return rules

def signature(rule):
    return {k: v for k, v in rule.items() if k not in META}

def expected_rule(in_port, mac, out_port):
    return dict(table='0', priority='100', in_port=str(in_port),
                dl_dst=mac.lower(), actions='output:' + str(out_port))

def has_rule(rules, expected):
    return any(signature(r) == expected for r in rules)

def preflight(rules, warm_rules):
    # Reject unknown matches/actions instead of pretending to model all OF pipelines.
    sigs = [signature(r) for r in rules]
    miss = [r for r in sigs if r.get('priority') == '0'
            and set(r) == {'table', 'priority', 'actions'} and r['table'] == '0'
            and r['actions'] in ('controller:65535', 'controller:65509', 'controller')]
    return (len(sigs) == len(warm_rules) + 1 and len(miss) == 1
            and all(sigs.count(r) == 1 for r in warm_rules))

def identity_matches(actual, expected):
    return all(actual.get(k) == expected.get(k) and k in actual and k in expected for k in IDENTITY)

class CaptureGate:
    def __init__(self, expected):
        self.expected, self.armed, self.accepted = expected, False, False

    def accept(self, actual):
        if self.armed and not self.accepted and identity_matches(actual, self.expected):
            self.accepted = True
            return True
        return False

def ping_result(stdout, stderr, rc, expected_count=1):
    """Linux iputils: partial reception may return 0 without a deadline.

    Preserve count and command status separately; unlike the legacy R5 parser,
    do not mark a legitimate partial-reception exit 0 as an instrument defect.
    """
    m = re.search(r'(\d+) packets transmitted, (\d+) (?:packets )?received', stdout)
    out = dict(stdout=stdout, stderr=stderr, rc=rc, tx=None, rx=None, valid=False, success=False)
    if not m:
        out['error'] = 'no_packet_counts'
        return out
    tx, rx = map(int, m.groups())
    out.update(tx=tx, rx=rx)
    if tx != expected_count or not 0 <= rx <= tx or rc not in (0, 1):
        out['error'] = 'counts_or_execution_invalid'
    elif (rc == 0 and rx == 0) or (rc == 1 and rx == tx):
        out['error'] = 'counts_exit_disagree'
    else:
        out.update(valid=True, success=(tx == rx and rc == 0))
    return out

def dump_once(bridge, timeout=None):
    start = time.perf_counter_ns()
    try:
        p = subprocess.run(['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', bridge],
                           capture_output=True, text=True,
                           timeout=PARAMETERS['call_s'] if timeout is None else timeout)
        end = time.perf_counter_ns()
        row = dict(start_ns=start, end_ns=end, rc=p.returncode, stdout=p.stdout, stderr=p.stderr)
        row['rules'] = parse_flows(p.stdout) if p.returncode == 0 else None
        row['error'] = None if p.returncode == 0 else 'nonzero_exit'
    except Exception as e:
        # Os-Ken/eventlet can expose a different TimeoutExpired class than the
        # one raised by stdlib communicate(). Preserve every observer failure.
        row = dict(start_ns=start, end_ns=time.perf_counter_ns(), rules=None, error=repr(e))
    return row

def observe(bridge, expected, timeout_s=None, reader=dump_once):
    timeout_s = PARAMETERS['confirm_s'] if timeout_s is None else timeout_s
    deadline = time.perf_counter() + timeout_s
    polls = []
    while time.perf_counter() < deadline:
        poll = reader(bridge, timeout=min(PARAMETERS['call_s'], max(0.001, deadline-time.perf_counter())))
        polls.append(poll)
        if poll.get('error'):
            if time.perf_counter() >= deadline and ('TimeoutExpired' in poll['error']):
                return dict(status='timed_out', confirmed_ns=None, polls=polls)
            return dict(status='tool_error', confirmed_ns=None, polls=polls)
        poll['matched'] = has_rule(poll['rules'], expected)
        if poll['matched'] and poll['end_ns'] / 1e9 <= deadline:
            return dict(status='confirmed', confirmed_ns=poll['end_ns'], polls=polls)
        time.sleep(min(PARAMETERS['poll_sleep_s'], max(0, deadline-time.perf_counter())))
    return dict(status='timed_out', confirmed_ns=None, polls=polls)
