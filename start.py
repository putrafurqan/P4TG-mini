import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import make_packet


def bytes_to_number(byte_list):
    number = 0
    for byte in byte_list:
        number = number * 256 + byte
    return number


# Step 1: build the packet 
packet = make_packet.make_packet()

# Step 2: report the resulting speed 
bits_per_packet = (config.FRAME_SIZE + 20) * 8

# One Gbit/s is one bit per nanosecond.
speed = config.PACKETS_PER_TIMER * bits_per_packet / config.TIMER_NANOSECONDS

packets_per_second = config.PACKETS_PER_TIMER / config.TIMER_NANOSECONDS * 1000000000
millions_of_packets = packets_per_second / 1000000

# Step 3: enable both packet generator 
for generator_port in config.GENERATOR_PORTS:
    bfrt.tf1.pktgen.port_cfg.mod(
        dev_port=generator_port,
        pktgen_enable=True,
    )

# Step 4: copy the packet into the switch 
bfrt.tf1.pktgen.pkt_buffer.mod(
    pkt_buffer_offset=config.MEMORY_POSITION,
    pkt_buffer_size=len(packet),
    buffer=bytes(packet),
)


# Step 5: Fill multicast group with 6 active Front Panel Port
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

# Step 6: Populate entry for multicast group at `pick_output_port` table
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

# Step 7: Populate entry for packet destination at `rewrite_per_port` table
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

# Step 6: start the timer 
bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
    app_id=config.GENERATOR_NUMBER,
    app_enable=True,
    pkt_len=len(packet),
    timer_nanosec=config.TIMER_NANOSECONDS,
    packets_per_batch_cfg=config.PACKETS_PER_TIMER - 1,
    batch_count_cfg=0,
    # Pipe local, so it is the same number in both pipes: 68.
    pipe_local_source_port=config.GENERATOR_PORTS[0],
    pkt_buffer_offset=config.MEMORY_POSITION,
)