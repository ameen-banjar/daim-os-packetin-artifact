"""Corrected, isolated three-arm application. Original collection code is untouched.

    A Unix control socket arms a cached identity only after external preflight.
    No file read or log write is performed inside the timed path, except the
    declared ovs-ofctl observation itself. The same observer serves all arms.
"""
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ipv4, icmp
from daim_core_bridge import DaimCoreBridge, PORT_FLOOD
import daim_core_bridge
from s56_measurement import CaptureGate, expected_rule, observe, PARAMETERS
import subprocess

CONFIG = json.loads(os.environ['S56_CONFIG'])
if CONFIG.get('library'):
    daim_core_bridge.LIB_PATH = Path(CONFIG['library'])

def emit(event, **kw):
    print(json.dumps(dict(event=event, **kw)), flush=True)

class CorrectedController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.mode = CONFIG['mode']
        self.gate = CaptureGate(CONFIG['identity'])
        self.table = {}
        self.core = None
        self.pre_packets = []
        self.adapter_ready = threading.Event()
        self.of_ready = threading.Event()
        self.executor_results = []
        if self.mode == 'reactive_osken':
            self.adapter_ready.set()
        elif self.mode == 'process_per_rule':
            self.core = DaimCoreBridge(executor=self.execute, mode=self.mode)
            self.adapter_ready.set()
        else:
            threading.Thread(target=self.build_adapter, daemon=True).start()
        threading.Thread(target=self.control, daemon=True).start()
        threading.Thread(target=self.ready, daemon=True).start()

    def execute(self, argv):
        args = [v.decode() if isinstance(v, bytes) else v for v in argv]
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=5)
            self.executor_results.append(dict(rc=p.returncode, stderr=p.stderr))
            return p.returncode
        except Exception as exc:
            self.executor_results.append(dict(rc=-1, error=repr(exc)))
            return -1

    def build_adapter(self):
        try:
            self.core = DaimCoreBridge(mode='persistent', persistent_port=CONFIG['persistent_port'])
            self.adapter_ready.set()
        except Exception as exc:
            emit('adapter_error', detail=repr(exc))

    def ready(self):
        if self.adapter_ready.wait(PARAMETERS['ready_s']) and self.of_ready.wait(PARAMETERS['ready_s']):
            emit('ready', mode=self.mode, trial_id=CONFIG['identity']['trial_id'])

    def control(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(CONFIG['control_socket'])
            server.listen(1)
            while True:
                conn, _ = server.accept()
                with conn:
                    cmd = json.loads(conn.recv(4096).decode())
                    ok = cmd.get('trial_id') == self.gate.expected['trial_id']
                    if ok and cmd.get('command') == 'arm':
                        self.gate.armed = True
                    conn.sendall(json.dumps(dict(ok=ok, armed=self.gate.armed,
                        accepted=self.gate.accepted, pre_packets=self.pre_packets)).encode() + b'\n')

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,
                [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])]))
        dp.send_msg(p.OFPBarrierRequest(dp))

    @set_ev_cls(ofp_event.EventOFPBarrierReply, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def barrier(self, ev):
        self.of_ready.set()

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        t0 = time.perf_counter_ns()
        msg, dp = ev.msg, ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        pkt = packet.Packet(msg.data)
        eth, ip, echo = pkt.get_protocol(ethernet.ethernet), pkt.get_protocol(ipv4.ipv4), pkt.get_protocol(icmp.icmp)
        if eth is None or not self.adapter_ready.is_set():
            return
        port = msg.match['in_port']
        actual = dict(trial_id=CONFIG['identity']['trial_id'], bridge=CONFIG['bridge'],
            dpid=dp.id, in_port=port, src_mac=eth.src, dst_mac=eth.dst,
            eth_type=eth.ethertype, src_ip=ip.src if ip else None,
            dst_ip=ip.dst if ip else None, ip_proto=ip.proto if ip else None,
            icmp_type=echo.type if echo else None,
            icmp_id=getattr(echo.data, 'id', None) if echo else None,
            icmp_seq=getattr(echo.data, 'seq', None) if echo else None)
        captured = self.gate.accept(actual)
        ts = dict(t_dispatch_enter_ns=t0)
        if self.mode == 'reactive_osken':
            ts['t_parse_done_ns'] = time.perf_counter_ns()
            table = self.table.setdefault(dp.id, {})
            table[eth.src] = port
            ts['t_state_update_done_ns'] = time.perf_counter_ns()
            out = table.get(eth.dst, o.OFPP_FLOOD)
            ts['t_decision_done_ns'] = time.perf_counter_ns()
            if out != o.OFPP_FLOOD:
                dp.send_msg(p.OFPFlowMod(datapath=dp, priority=100,
                    match=p.OFPMatch(in_port=port, eth_dst=eth.dst),
                    instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, [p.OFPActionOutput(out)])]))
            ts['t_flowmod_sent_ns'] = time.perf_counter_ns()
        else:
            ts['t_pre_ctypes_ns'] = time.perf_counter_ns()
            out = self.core.packet_in(CONFIG['bridge'], port,
                    [int(v,16) for v in eth.src.split(':')],
                    [int(v,16) for v in eth.dst.split(':')], eth.ethertype)
            ts['t_post_ctypes_ns'] = time.perf_counter_ns()
            if captured:
                c = self.core.last_timing()
                ts.update({'c_'+k: v for k,v in c.items() if k != 'installed'})
            if out == PORT_FLOOD:
                out = o.OFPP_FLOOD
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=port,
            actions=[p.OFPActionOutput(out)], data=msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None))
        ts['t_packetout_sent_ns'] = time.perf_counter_ns()
        if captured:
            observed = observe(CONFIG.get('observer_bridge', CONFIG['bridge']),
                expected_rule(port, eth.dst, CONFIG.get('observer_out_port', CONFIG['out_port'])))
            emit('timing', mode=self.mode, identity=actual, timestamps=ts,
                 observation=observed, chosen_out_port=out,
                 executor_results=list(self.executor_results))
        elif len(self.pre_packets) < 100:
            self.pre_packets.append(dict(identity=actual, at_ns=t0, armed=self.gate.armed))
