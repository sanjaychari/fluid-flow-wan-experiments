#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse

ROUTERS_PER_GROUP=8
TERMINALS_PER_ROUTER=4
GROUPS=33
GLOBAL_CHANNELS=4
LOCAL_MBPS=42000
GLOBAL_MBPS=37600
TERMINAL_MBPS=42000
BUFFER_GB=100


def global_targets(router_id: int):
    # Mirror src/networks/model-net/dragonfly.c with USE_DIRECT_SCHEME=1.
    group=router_id//ROUTERS_PER_GROUP
    local=router_id%ROUTERS_PER_GROUP
    first=local
    out=[]
    for _ in range(GLOBAL_CHANNELS):
        target_group=first
        if target_group==group:
            target_group=GROUPS-1
        my_pos=group%ROUTERS_PER_GROUP
        if group==GROUPS-1:
            my_pos=target_group%ROUTERS_PER_GROUP
        out.append(target_group*ROUTERS_PER_GROUP+my_pos)
        first += ROUTERS_PER_GROUP
    return out


def main():
    p=argparse.ArgumentParser(); p.add_argument("output",type=Path); a=p.parse_args()
    lines=["topology:","  switches:"]
    total=GROUPS*ROUTERS_PER_GROUP
    for rid in range(total):
        group=rid//ROUTERS_PER_GROUP
        local_start=group*ROUTERS_PER_GROUP
        local_targets=[x for x in range(local_start,local_start+ROUTERS_PER_GROUP) if x!=rid]
        targets=[(x,LOCAL_MBPS) for x in local_targets]+[(x,GLOBAL_MBPS) for x in global_targets(rid)]
        lines += [f"    R{rid:03d}:", f"      terminals: {TERMINALS_PER_ROUTER}",
                  f'      terminal_bandwidth: "{TERMINAL_MBPS} Mbps"', f'      switch_buffer: "{BUFFER_GB} Gb"',
                  "      connections:"]
        for dst,bw in targets:
            lines.append(f'        R{dst:03d}: "{bw} Mbps"')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(lines)+"\n")
    print(f"wrote {a.output}: switches={total} terminals={total*TERMINALS_PER_ROUTER} directed_links={total*11}")

if __name__=="__main__": main()
