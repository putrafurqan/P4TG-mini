import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import make_packet
import rate


# On Tofino a device port number is (pipe * 128) + the port number inside that pipe.
PORTS_PER_PIPE = 128


def bytes_to_number(byte_list):
    number = 0
    for byte in byte_list:
        number = number * 256 + byte
    return number


def round_up(value, step):
    remainder = value % step
    if remainder == 0:
        return value
    return value + step - remainder


# Step 1: work out which generator slot each frame size will use

slots_available = config.MAX_SLOTS_PER_PIPE * len(config.GENERATOR_PORTS)

if len(config.STREAMS) == 0:
    raise ValueError("STREAMS in config.py is empty. Add at least one frame size.")

if len(config.STREAMS) > slots_available:
    raise ValueError(
        f"config.py asks for {len(config.STREAMS)} frame sizes but only "
        f"{slots_available} generator slots exist "
        f"({config.MAX_SLOTS_PER_PIPE} per pipe, {len(config.GENERATOR_PORTS)} pipes)."
    )

# Slots are handed out in order: the first pipe is filled up before the second
# pipe is touched at all.
streams = []
next_free_byte = [0] * len(config.GENERATOR_PORTS)

for position, wanted in enumerate(config.STREAMS):

    pipe = position // config.MAX_SLOTS_PER_PIPE
    slot = position % config.MAX_SLOTS_PER_PIPE

    packet = make_packet.make_packet(wanted["size"])

    # Each packet has to start on a 16-byte boundary in the pipe's memory.
    offset = next_free_byte[pipe]
    next_free_byte[pipe] = round_up(offset + len(packet), config.PKT_BUFFER_ALIGNMENT)

    batch, timer, achieved = rate.solve_rate(wanted["pps"])

    streams.append({
        "size": wanted["size"],
        "wanted_pps": wanted["pps"],
        "pipe": pipe,
        "slot": slot,
        "generator_port": config.GENERATOR_PORTS[pipe],
        "packet": packet,
        "offset": offset,
        "batch": batch,
        "timer": timer,
        "achieved_pps": achieved,
        "gbps": rate.gigabits_per_second(achieved, wanted["size"]),
    })


# Step 2: refuse to start if a pipe has been asked for more than it can give

for pipe in range(len(config.GENERATOR_PORTS)):

    memory_used = next_free_byte[pipe]
    if memory_used > config.PKT_BUFFER_BYTES_PER_PIPE:
        raise ValueError(
            f"Pipe {pipe} needs {memory_used} bytes of packet memory but only "
            f"{config.PKT_BUFFER_BYTES_PER_PIPE} bytes exist. Use fewer or smaller frames."
        )

    speed_used = 0
    for stream in streams:
        if stream["pipe"] == pipe:
            speed_used = speed_used + stream["gbps"]

    if speed_used > config.PIPE_MAX_GBPS:
        raise ValueError(
            f"Pipe {pipe} is asked for {speed_used:.2f} Gbit/s but can only produce "
            f"{config.PIPE_MAX_GBPS} Gbit/s. Lower the pps values."
        )


# Step 3: show what is about to be set up

print()
print(f"{'size':>6}  {'pipe':>4}  {'slot':>4}  {'offset':>7}  {'batch':>6}  {'timer ns':>9}  {'wanted pps':>13}  {'actual pps':>13}  {'Gbit/s':>8}  {'share':>7}")

total_pps = 0
for stream in streams:
    total_pps = total_pps + stream["achieved_pps"]

total_gbps = 0
for stream in streams:
    total_gbps = total_gbps + stream["gbps"]

for stream in streams:
    share = stream["achieved_pps"] / total_pps * 100
    print(
        f"{stream['size']:>6}  {stream['pipe']:>4}  {stream['slot']:>4}  "
        f"{stream['offset']:>7}  {stream['batch']:>6}  {stream['timer']:>9,}  "
        f"{stream['wanted_pps']:>13,}  {stream['achieved_pps']:>13,.1f}  "
        f"{stream['gbps']:>8.3f}  {share:>6.2f}%"
    )

print()
for pipe in range(len(config.GENERATOR_PORTS)):
    pipe_gbps = 0
    pipe_slots = 0
    for stream in streams:
        if stream["pipe"] == pipe:
            pipe_gbps = pipe_gbps + stream["gbps"]
            pipe_slots = pipe_slots + 1
    if pipe_slots > 0:
        print(
            f"Pipe {pipe}: {pipe_slots} of {config.MAX_SLOTS_PER_PIPE} slots, "
            f"{next_free_byte[pipe]} of {config.PKT_BUFFER_BYTES_PER_PIPE} bytes, "
            f"{pipe_gbps:.3f} Gbit/s"
        )

print(f"Total: {total_pps:,.0f} packets per second, {total_gbps:.3f} Gbit/s")
print("Every one of the six ports receives a copy of this whole mix.")
print()


# Step 4: turn on the packet generators that are actually being used

pipes_used = []
for stream in streams:
    if stream["pipe"] not in pipes_used:
        pipes_used.append(stream["pipe"])

for pipe in pipes_used:
    bfrt.tf1.pktgen.port_cfg.mod(
        dev_port=config.GENERATOR_PORTS[pipe],
        pktgen_enable=True,
    )


# Step 5: copy every packet into the switch

for stream in streams:
    bfrt.tf1.pktgen.pkt_buffer.mod(
        pipe=stream["pipe"],
        pkt_buffer_offset=stream["offset"],
        pkt_buffer_size=len(stream["packet"]),
        buffer=bytes(stream["packet"]),
    )


# Step 6: Fill multicast group with 6 active Front Panel Port
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

# Step 7: Populate entry for multicast group at `pick_output_port` table
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

# Step 8: Populate entry for packet destination at `rewrite_per_port` table
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


# Step 9: start every timer, which is what actually sends the traffic
#
# `pipe` picks which pipe's generator this slot belongs to, so the same slot
# number on the other pipe is left alone. `pipe_local_source_port` is the port
# number counted from the start of that pipe, so it is the same value on both.

for stream in streams:
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
        pipe=stream["pipe"],
        app_id=stream["slot"],
        app_enable=True,
        pkt_len=len(stream["packet"]),
        timer_nanosec=stream["timer"],
        packets_per_batch_cfg=stream["batch"] - 1,
        batch_count_cfg=0,
        pipe_local_source_port=stream["generator_port"] % PORTS_PER_PIPE,
        pkt_buffer_offset=stream["offset"],
    )

print(f"Started {len(streams)} frame sizes.")
