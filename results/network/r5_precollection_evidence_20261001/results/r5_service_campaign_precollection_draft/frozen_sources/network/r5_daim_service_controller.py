"""Campaign-only name resolution around the unchanged DAIM application/Core.

The unprivileged controller cannot query OVSDB's root-owned socket. The harness
therefore supplies its exact DPID/name mapping before switch connection. No
global socket permission change and no packet/learning/Flow-Mod policy change.
"""
import json
import os
from pathlib import Path
import subprocess
import daim_bridge_controller as original

def checked_executor(argv):
    args=[x.decode() if isinstance(x,bytes) else x for x in argv]
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:
        original.emit('adapter_command_failed',argv=args,rc=p.returncode,stdout=p.stdout,stderr=p.stderr)
    return p.returncode

original.run_ovs_command=checked_executor

class CampaignDaimController(original.DaimBridgeController):
    def _resolve_bridge_name(self,dpid):
        if dpid not in self.dpid_to_bridge:
            mapping=json.loads(Path(os.environ['DAIM_BRIDGE_MAP']).read_text())
            name=mapping.get(f'{dpid:016x}')
            if not name: raise RuntimeError(f'Unmapped experimental DPID {dpid:016x}')
            self.dpid_to_bridge[dpid]=name
        return self.dpid_to_bridge[dpid]
