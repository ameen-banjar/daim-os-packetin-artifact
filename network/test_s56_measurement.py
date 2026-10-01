import time
import unittest
from s56_measurement import *

class MeasurementTests(unittest.TestCase):
    def test_identity_arming_and_duplicate(self):
        expected={k:i for i,k in enumerate(IDENTITY)}
        g=CaptureGate(expected)
        self.assertFalse(g.accept(expected))
        g.armed=True
        for key in IDENTITY:
            wrong=dict(expected);wrong[key]=-1
            self.assertFalse(g.accept(wrong),key)
        self.assertTrue(g.accept(expected))
        self.assertFalse(g.accept(expected))

    def test_no_fields_joined_between_rules(self):
        expected=expected_rule(1,'02:00:00:00:00:02',2)
        text=' cookie=0x0, priority=100,in_port=1,dl_dst=02:00:00:00:00:02 actions=output:3\n cookie=0x0,priority=100,in_port=2,dl_dst=02:00:00:00:00:03 actions=output:2'
        self.assertFalse(has_rule(parse_flows(text),expected))
        text='cookie=0x0,dl_dst=02:00:00:00:00:02,table=0,in_port=1,priority=100 actions=output:2'
        self.assertTrue(has_rule(parse_flows(text),expected))
        self.assertFalse(has_rule(parse_flows(text.replace('actions=output:2','actions=output:2,CONTROLLER:65535')),expected))

    def test_preflight_rejects_wildcard_unknown_duplicate(self):
        w=[expected_rule(2,'02:00:00:00:00:03',3),expected_rule(3,'02:00:00:00:00:02',2)]
        rules=w+[dict(table='0',priority='0',actions='controller:65535')]
        self.assertTrue(preflight(rules,w))
        for bad in (dict(table='0',priority='1',actions='normal'),w[0],dict(table='1',priority='0',actions='drop')):
            self.assertFalse(preflight(rules+[bad],w))

    def test_ping_extremes_partial_and_errors(self):
        for tx,rx,rc,valid,success in [(1,1,0,True,True),(1,0,1,True,False),(2,1,0,True,False),(1,0,0,False,False),(1,1,1,False,False),(1,0,2,False,False)]:
            r=ping_result(f'{tx} packets transmitted, {rx} received', '',rc,tx)
            self.assertEqual((r['valid'],r['success']),(valid,success))
        self.assertFalse(ping_result('', 'error', 2)['valid'])

    def test_observer_success_timeout_error(self):
        rule=expected_rule(1,'02:00:00:00:00:02',2)
        def result(rules,error=None):
            now=time.perf_counter_ns()
            return dict(start_ns=now,end_ns=now,rc=0,rules=rules,error=error)
        self.assertEqual(observe('x',rule,0.02,lambda *a,**k:result([rule]))['status'],'confirmed')
        self.assertEqual(observe('x',rule,0.002,lambda *a,**k:result([]))['status'],'timed_out')
        self.assertEqual(observe('x',rule,0.02,lambda *a,**k:result(None,'permission'))['status'],'tool_error')

if __name__=='__main__': unittest.main()
