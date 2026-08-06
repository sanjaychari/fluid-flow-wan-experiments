#!/usr/bin/env python3

from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    case = root / "results" / "correctness"
    case.mkdir(parents=True, exist_ok=True)

    # CODES topology:
    #
    #   T0 --\
    #         S0 ---- 10 Gbps ---- S1 -- T2
    #   T1 --/                     |  \-- T3
    #
    # Both 10-Gbit flows share S0 -> S1.
    (case / "topology.yaml").write_text("""\
topology:
  switches:
    S0:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "1000 Gb"
      connections:
        S1: "10 Gbps"

    S1:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "1000 Gb"
      connections:
        S0: "100 Gbps"
""")

    # Two equal flows sharing the 10-Gbps S0->S1 bottleneck.
    (case / "traffic.csv").write_text("""\
interval,flow_id,source_terminal,destination_terminal,offered_gbit
0,1,0,2,10
0,2,1,3,10
""")

    # Only fluid-segment logging is needed to inspect CODES's max-min allocation.
    (case / "codes.yaml").write_text("""\
schema_version: 1

topology:
  format: groups
  params:
    message_size: 32768
    pe_mem_factor: 1024
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        fluid-flow-wan-switch-lp: 2
        fluid-flow-wan-terminal-lp: 4

sections:
  fluid_flow_wan:
    topology_yaml_file: "topology.yaml"
    traffic_trace_file: "traffic.csv"

    interval_seconds: 1
    num_send_intervals: 1
    num_drain_intervals: 8

    egress_model: pdes
    debug_prints: 0
    backpressure_delay_ms: 1.0

    pause_high_watermark_fraction: 0.999999
    pause_low_watermark_fraction: 0.999998

    fluid_segment_log_path: "fluid-segment-events.csv"
""")

    # Equivalent SimGrid bottleneck.
    # 100 Gbps = 12.5 GB/s
    # 10 Gbps  = 1.25 GB/s
    (case / "platform.xml").write_text("""\
<?xml version='1.0'?>
<!DOCTYPE platform SYSTEM "https://simgrid.org/simgrid.dtd">
<platform version="4.1">
  <zone id="AS0" routing="Full">
    <host id="T0" speed="1Gf"/>
    <host id="T1" speed="1Gf"/>
    <host id="T2" speed="1Gf"/>
    <host id="T3" speed="1Gf"/>

    <link id="T0_up" bandwidth="12.5GBps" latency="0s"/>
    <link id="T1_up" bandwidth="12.5GBps" latency="0s"/>
    <link id="bottleneck" bandwidth="1.25GBps" latency="0s"/>
    <link id="T2_down" bandwidth="12.5GBps" latency="0s"/>
    <link id="T3_down" bandwidth="12.5GBps" latency="0s"/>

    <route src="T0" dst="T2" symmetrical="NO">
      <link_ctn id="T0_up"/>
      <link_ctn id="bottleneck"/>
      <link_ctn id="T2_down"/>
    </route>

    <route src="T1" dst="T3" symmetrical="NO">
      <link_ctn id="T1_up"/>
      <link_ctn id="bottleneck"/>
      <link_ctn id="T3_down"/>
    </route>
  </zone>
</platform>
""")

    print(case)


if __name__ == "__main__":
    main()
