"""Real OpenFlow 1.3 controller whose Packet-In handling is delegated to the
DAIM Core NO_RULE callback via daim_core_bridge.DaimCoreBridge, instead of a
Python dict (contrast with osken_learning_controller.py). The controller
still owns: the OpenFlow session, the table-miss rule, dpid<->bridge name
resolution, and sending the buffered first packet back out (PacketOut) --
DAIM Core owns the MAC-learning decision, the forwarding-table record, and
installing the persistent OVS flow for learned destinations.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet

from daim_core_bridge import DaimCoreBridge, PORT_FLOOD


def run_ovs_command(argv):
    args = [a.decode() if isinstance(a, bytes) else a for a in argv]
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode


def mac_str_to_bytes(mac):
    return [int(part, 16) for part in mac.split(":")]


class DaimBridgeController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge = DaimCoreBridge(run_ovs_command)
        self.dpid_to_bridge = {}

    def _resolve_bridge_name(self, dpid):
        name = self.dpid_to_bridge.get(dpid)
        if name:
            return name
        datapath_id = "%016x" % dpid
        result = subprocess.run(
            ["ovs-vsctl", "--bare", "--columns=name", "find", "bridge",
             'datapath_id="%s"' % datapath_id],
            capture_output=True, text=True,
        )
        name = result.stdout.strip().strip('"')
        if name:
            self.dpid_to_bridge[dpid] = name
        return name or datapath_id

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        p = dp.ofproto_parser
        o = dp.ofproto
        self._resolve_bridge_name(dp.id)
        match = p.OFPMatch()
        actions = [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)]
        dp.send_msg(p.OFPFlowMod(
            datapath=dp, priority=0, match=match,
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)],
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        p = dp.ofproto_parser
        o = dp.ofproto
        eth = packet.Packet(msg.data).get_protocol(ethernet.ethernet)
        if not eth:
            return

        bridge = self._resolve_bridge_name(dp.id)
        in_port = msg.match["in_port"]

        out_port = self.bridge.packet_in(
            bridge, in_port,
            mac_str_to_bytes(eth.src), mac_str_to_bytes(eth.dst),
            eth.ethertype,
        )

        actions = [p.OFPActionOutput(o.OFPP_FLOOD if out_port == PORT_FLOOD else out_port)]
        dp.send_msg(p.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions,
            data=msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None,
        ))
