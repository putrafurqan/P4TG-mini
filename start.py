import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import flow_plan


def bytes_to_number(byte_list):
    number = 0
    for byte in byte_list:
        number = number * 256 + byte
    return number


def choose_profile():
    names = list(config.PROFILES.keys())

    print("Available profiles:")
    for index, name in enumerate(names):
        marker = " (default)" if name == config.ACTIVE_PROFILE else ""
        print(f"  {index}: {name}{marker}")

    while True:
        choice = input(f"Profile to run [{config.ACTIVE_PROFILE}]: ").strip()

        if choice == "":
            return config.ACTIVE_PROFILE
        if choice in config.PROFILES:
            return choice
        if choice.isdigit() and 0 <= int(choice) < len(names):
            return names[int(choice)]

        print(f"'{choice}' is not a valid profile name or index, try again.")


def report_speed(profile, plan):
    print("\nFlow rates:")

    total_pps = 0
    total_gbit = 0.0

    for flow in profile["flows"]:
        entries = [e for e in plan if e["flow_name"] == flow["name"]]
        pipes = [e["pipe"] for e in entries]
        per_pipe_pps = (entries[0]["packets_per_batch_cfg"] + 1) / entries[0]["timer_nanosec"] * 1_000_000_000
        flow_pps = per_pipe_pps * len(entries)
        flow_gbit = flow_pps * (flow["frame_size"] + 20) * 8 / 1_000_000_000

        print(f"  {flow['name']}: {flow['frame_size']}B, pipes={pipes}, {per_pipe_pps:.1f} pps/pipe x "
              f"{len(entries)} pipes = {flow_pps:.1f} pps, {flow_gbit:.4f} Gbit/s")

        total_pps += flow_pps
        total_gbit += flow_gbit

    print(f"  TOTAL: {total_pps:.1f} pps, {total_gbit:.4f} Gbit/s\n")


# Step 1: choose and build the flow plan
profile_name = choose_profile()
profile = config.PROFILES[profile_name]
plan = flow_plan.build_flow_plan(profile)

print(f"Running profile: {profile_name}")
report_speed(profile, plan)

# Step 2: enable both packet generator
for generator_port in config.GENERATOR_PORTS:
    bfrt.tf1.pktgen.port_cfg.mod(
        dev_port=generator_port,
        pktgen_enable=True,
    )

# Step 3: copy each flow's packet into the switch, once per flow
# Buffer writes use the padded bytes; pkt_len (Step 7) uses the true length.
for flow in profile["flows"]:
    entry = next(e for e in plan if e["flow_name"] == flow["name"])
    bfrt.tf1.pktgen.pkt_buffer.mod(
        pkt_buffer_offset=entry["pkt_buffer_offset"],
        pkt_buffer_size=len(entry["buffer_bytes"]),
        buffer=bytes(entry["buffer_bytes"]),
    )

# Step 4: Fill multicast group with 6 active Front Panel Port
output_ports = []
for port in config.PORTS:
    output_ports.append(port["dev_port"])

try:
    bfrt.pre.mgid.delete(MGID=config.MULTICAST_GROUP)
except:
    pass
try:
    bfrt.pre.node.delete(MULTICAST_NODE_ID=config.MULTICAST_GROUP)
except:
    pass

bfrt.pre.node.entry(
    MULTICAST_NODE_ID=config.MULTICAST_GROUP,
    MULTICAST_RID=0,
    MULTICAST_LAG_ID=[],
    DEV_PORT=output_ports,
).push()

bfrt.pre.mgid.entry(
    MGID=config.MULTICAST_GROUP,
    MULTICAST_NODE_ID=[config.MULTICAST_GROUP],
    MULTICAST_NODE_L1_XID_VALID=[False],
    MULTICAST_NODE_L1_XID=[0],
).push()

# Step 5: Populate entry for multicast group at `pick_output_port` table
for generator_port in config.GENERATOR_PORTS:
    try:
        bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.delete(
            ingress_port=generator_port,
        )
    except:
        pass

    bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.add_with_send_to_group(
        ingress_port=generator_port,
        group_id=config.MULTICAST_GROUP,
    )

# Step 6: Populate entry for packet destination at `rewrite_per_port` table
for port in config.PORTS:
    try:
        bfrt.p4tg_mini.pipe.MyEgress.rewrite_per_port.delete(
            egress_port=port["dev_port"],
        )
    except:
        pass

    bfrt.p4tg_mini.pipe.MyEgress.rewrite_per_port.add_with_rewrite_addresses(
        egress_port=port["dev_port"],
        new_mac=bytes_to_number(port["mac"]),
        new_ip=bytes_to_number(port["ip"]),
    )

# Step 7: start the timer, once per (flow, pipe)
# `pipe` selects the app's pipe; `pipe_local_source_port` is the port number local to that pipe, not the global dev_port.
for entry in plan:
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
        app_id=entry["app_id"],
        app_enable=True,
        pkt_len=len(entry["packet"]),
        timer_nanosec=entry["timer_nanosec"],
        packets_per_batch_cfg=entry["packets_per_batch_cfg"],
        batch_count_cfg=0,
        pipe=entry["pipe"],
        pipe_local_source_port=entry["local_port"],
        pkt_buffer_offset=entry["pkt_buffer_offset"],
    )
