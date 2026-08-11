import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import make_packet

# Step 1: build the packet 
packet = make_packet.make_packet()

# Step 2: report the resulting speed 
bits_per_packet = (config.FRAME_SIZE + 20) * 8

# One Gbit/s is one bit per nanosecond.
speed = config.PACKETS_PER_TIMER * bits_per_packet / config.TIMER_NANOSECONDS

packets_per_second = config.PACKETS_PER_TIMER / config.TIMER_NANOSECONDS * 1000000000
millions_of_packets = packets_per_second / 1000000

# Step 3: enable the packet generator 
bfrt.tf1.pktgen.port_cfg.mod(
    dev_port=config.GENERATOR_PORT,
    pktgen_enable=True,
)

# Step 4: copy the packet into the switch 
bfrt.tf1.pktgen.pkt_buffer.mod(
    pkt_buffer_offset=config.MEMORY_POSITION,
    pkt_buffer_size=len(packet),
    buffer=bytes(packet),
)

# Step 5: choose the output port 
try:
    bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.delete(
        ingress_port=config.GENERATOR_PORT,
    )
except:
    pass

bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.add_with_send_to_port(
    ingress_port=config.GENERATOR_PORT,
    port_number=config.OUTPUT_PORT,
)

# Step 6: start the timer 
bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
    app_id=config.GENERATOR_NUMBER,
    app_enable=True,
    pkt_len=len(packet),
    timer_nanosec=config.TIMER_NANOSECONDS,
    packets_per_batch_cfg=config.PACKETS_PER_TIMER - 1,
    batch_count_cfg=0,
    pipe_local_source_port=config.GENERATOR_PORT,
    pkt_buffer_offset=config.MEMORY_POSITION,
)