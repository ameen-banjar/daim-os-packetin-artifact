"""Direct Os-Ken baseline controller for the Stage-2 comparison: no DAIM Core,
no ctypes bridge, no C adapter. As soon as a switch connects, it proactively
installs the same rule used by every other Stage-2 mode
(priority=100, eth_type=IPv4, actions=NORMAL) using Os-Ken's native OpenFlow
API, then sends a Barrier Request and times until the Barrier Reply -- the
standard way to confirm a switch has finished processing a Flow-Mod, giving
a timing semantic comparable to the other modes' synchronous CLI calls.

Emits one JSON line per confirmed install to stdout:
    {"event": "flow_confirmed", "dpid": <int>, "elapsed_us": <float>}
"""
import json
import time

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3


class DirectBaselineController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_ns = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        p = dp.ofproto_parser
        o = dp.ofproto

        start = time.perf_counter_ns()
        self.start_ns[dp.id] = start

        match = p.OFPMatch(eth_type=0x0800)
        actions = [p.OFPActionOutput(o.OFPP_NORMAL)]
        instructions = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)]
        flow_mod = p.OFPFlowMod(datapath=dp, priority=100, match=match, instructions=instructions)
        dp.send_msg(flow_mod)
        dp.send_msg(p.OFPBarrierRequest(dp))

    @set_ev_cls(ofp_event.EventOFPBarrierReply, MAIN_DISPATCHER)
    def barrier_reply(self, ev):
        dp = ev.msg.datapath
        end = time.perf_counter_ns()
        start = self.start_ns.pop(dp.id, None)
        if start is None:
            return
        elapsed_us = (end - start) / 1000.0
        print(json.dumps({"event": "flow_confirmed", "dpid": dp.id, "elapsed_us": elapsed_us}), flush=True)
