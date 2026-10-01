"""Same campaign-only DPID/name resolver as DAIM; forwarding is unchanged."""
import json
import os
from pathlib import Path
import osken_reactive_baseline_controller as original

class CampaignOskenController(original.MatchedReactiveBaselineController):
    def _resolve_bridge_name(self,dpid):
        if dpid not in self.dpid_to_bridge:
            mapping=json.loads(Path(os.environ['DAIM_BRIDGE_MAP']).read_text())
            name=mapping.get(f'{dpid:016x}')
            if not name: raise RuntimeError(f'Unmapped experimental DPID {dpid:016x}')
            self.dpid_to_bridge[dpid]=name
        return self.dpid_to_bridge[dpid]
