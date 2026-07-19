from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet

class LearningController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.mac_to_port = {}
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp=ev.msg.datapath; p=dp.ofproto_parser; o=dp.ofproto
        m=p.OFPMatch(); a=[p.OFPActionOutput(o.OFPP_CONTROLLER,o.OFPCML_NO_BUFFER)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=m, instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,a)]))
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg=ev.msg; dp=msg.datapath; p=dp.ofproto_parser; o=dp.ofproto; dpid=dp.id
        eth=packet.Packet(msg.data).get_protocol(ethernet.ethernet)
        if not eth: return
        self.mac_to_port.setdefault(dpid,{})[eth.src]=msg.match['in_port']
        out=self.mac_to_port[dpid].get(eth.dst,o.OFPP_FLOOD)
        actions=[p.OFPActionOutput(out)]
        if out != o.OFPP_FLOOD:
            match=p.OFPMatch(in_port=msg.match['in_port'], eth_dst=eth.dst)
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=10, match=match, instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,actions)]))
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=msg.match['in_port'], actions=actions, data=msg.data if msg.buffer_id==o.OFP_NO_BUFFER else None))
