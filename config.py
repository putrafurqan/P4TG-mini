# Variable Configuration for P4TG-Mini

# PORTS CONFIGURATION
# PKTGEN PORT: 68 on pipe 0, 196 on pipe 1
GENERATOR_PORTS = [68, 196]
# SET ALL 6 PORTS TO MULTICAST GROUP 1
MULTICAST_GROUP = 1

# SET EACH PORT IDENTITY (ETHERNET SRC DST)
PORTS = [
    {"dev_port": 188, "mac": [0x10, 0x41, 0x6d, 0x18, 0x65, 0xfa], "ip": [192, 168, 1, 11]},  # 1/0  -> eth1
    {"dev_port": 184, "mac": [0x10, 0x41, 0x6d, 0x18, 0x65, 0xfb], "ip": [192, 168, 1, 13]},  # 2/0  -> eth3
    {"dev_port": 156, "mac": [0x10, 0x41, 0x6d, 0x18, 0x67, 0x50], "ip": [192, 168, 1, 15]},  # 9/0  -> eth5
    {"dev_port": 152, "mac": [0x10, 0x41, 0x6d, 0x18, 0x67, 0x51], "ip": [192, 168, 1, 16]},  # 10/0 -> eth6
    {"dev_port": 0,   "mac": [0x10, 0x41, 0x6d, 0x18, 0x66, 0xf2], "ip": [192, 168, 1, 17]},  # 17/0 -> eth7
    {"dev_port": 4,   "mac": [0x10, 0x41, 0x6d, 0x18, 0x66, 0xf3], "ip": [192, 168, 1, 18]},  # 18/0 -> eth8
]


# STREAMS
#
# The hardware has eight generator slots per pipe and there are two pipes, so
# sixteen different packets can be in the air at once. That is the ceiling: a
# seventeenth stack needs a second session.
#
# Each entry is one slot:
#
#   pipe               0 or 1, choosing which generator engine runs it
#   app_id             0 to 7, the slot within that engine
#   builder            a name from BUILDERS in make_packet.py
#   frame_size         size on the cable including the 4 byte error check.
#                      One size per slot: the hardware cannot vary it per packet
#   timer_ns           nanoseconds between bursts
#   packets_per_timer  packets produced each burst. One gives the smoothest traffic
#   outer              "ipv4" or "ipv6", saying which header the address range
#                      rewrites. The switch parses down to the first IP header
#                      only, so this is always the outermost one
#   addr_base          the bottom of the destination address range
#   addr_mask          how many addresses the range holds. Always a power of two
#                      minus one, because the switch applies it as a mask
#
# The slot number the switch sees is global: pipe 0 uses 0 to 7 and pipe 1 uses
# 8 to 15. start.py works that out, it is not written here.
#
# Rate: timer_ns is set so each stream runs at about 2 Gbit/s. All sixteen are
# multicast to all six ports, so every port carries the sum, about 32 Gbit/s.
# Raising these needs the per pipe generator ceiling checked first.

STREAMS = [
    # Pipe 0 -- plain stacks, tag stacks and label stacks.
    {"name": "ipv4_udp",            "pipe": 0, "app_id": 0, "builder": "ipv4_udp",
     "frame_size": 64,   "timer_ns": 336,  "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 0, 0],  "addr_mask": 0x000000FF},

    {"name": "ipv4_tcp",            "pipe": 0, "app_id": 1, "builder": "ipv4_tcp",
     "frame_size": 128,  "timer_ns": 592,  "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 1, 0],  "addr_mask": 0x000000FF},

    {"name": "vlan_ipv4_udp",       "pipe": 0, "app_id": 2, "builder": "vlan_ipv4_udp",
     "frame_size": 256,  "timer_ns": 1104, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 2, 0],  "addr_mask": 0x0000000F},

    {"name": "qinq_ipv4_tcp",       "pipe": 0, "app_id": 3, "builder": "qinq_ipv4_tcp",
     "frame_size": 512,  "timer_ns": 2128, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 3, 0],  "addr_mask": 0x0000000F},

    {"name": "mpls_ipv4_udp",       "pipe": 0, "app_id": 4, "builder": "mpls_ipv4_udp",
     "frame_size": 1024, "timer_ns": 4176, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 4, 0],  "addr_mask": 0x000000FF},

    {"name": "mpls_stack_ipv4_udp", "pipe": 0, "app_id": 5, "builder": "mpls_stack_ipv4_udp",
     "frame_size": 1518, "timer_ns": 6152, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 0, 5, 0],  "addr_mask": 0x000000FF},

    {"name": "ipv6_udp",            "pipe": 0, "app_id": 6, "builder": "ipv6_udp",
     "frame_size": 96,   "timer_ns": 464,  "packets_per_timer": 1,
     "outer": "ipv6", "addr_base": 0x0A000600, "addr_mask": 0x000000FF},

    {"name": "ipv6_tcp",            "pipe": 0, "app_id": 7, "builder": "ipv6_tcp",
     "frame_size": 192,  "timer_ns": 848,  "packets_per_timer": 1,
     "outer": "ipv6", "addr_base": 0x0A000700, "addr_mask": 0x000000FF},

    # Pipe 1 -- tunnels, and the two stacks with no layer 4 ports.
    {"name": "gre_ipv4_tcp",        "pipe": 1, "app_id": 0, "builder": "gre_ipv4_tcp",
     "frame_size": 128,  "timer_ns": 592,  "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 0, 0],  "addr_mask": 0x000000FF},

    {"name": "gre_bridged",         "pipe": 1, "app_id": 1, "builder": "gre_bridged",
     "frame_size": 256,  "timer_ns": 1104, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 1, 0],  "addr_mask": 0x000000FF},

    # The widest range of the sixteen: 65536 destinations. The switch applies
    # the mask with an OR, so every bit the mask varies has to be zero in the
    # base, which is why this one sits on its own /16 rather than in 10.1.
    {"name": "vxlan",               "pipe": 1, "app_id": 2, "builder": "vxlan",
     "frame_size": 1518, "timer_ns": 6152, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 2, 0, 0],  "addr_mask": 0x0000FFFF},

    {"name": "geneve",              "pipe": 1, "app_id": 3, "builder": "geneve",
     "frame_size": 512,  "timer_ns": 2128, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 3, 0],  "addr_mask": 0x000000FF},

    {"name": "gtpu",                "pipe": 1, "app_id": 4, "builder": "gtpu",
     "frame_size": 384,  "timer_ns": 1616, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 4, 0],  "addr_mask": 0x000000FF},

    {"name": "esp",                 "pipe": 1, "app_id": 5, "builder": "esp",
     "frame_size": 64,   "timer_ns": 336,  "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 5, 0],  "addr_mask": 0x000000FF},

    {"name": "segment_routing",     "pipe": 1, "app_id": 6, "builder": "segment_routing",
     "frame_size": 256,  "timer_ns": 1104, "packets_per_timer": 1,
     "outer": "ipv6", "addr_base": 0x0A010600, "addr_mask": 0x000000FF},

    {"name": "icmp",                "pipe": 1, "app_id": 7, "builder": "icmp",
     "frame_size": 1024, "timer_ns": 4176, "packets_per_timer": 1,
     "outer": "ipv4", "addr_base": [10, 1, 7, 0],  "addr_mask": 0x000000FF},
]


# PACKET CONTENTS
#
# Source addresses are fixed. Destination addresses are placeholders: the switch
# writes the real destination MAC per port, and the destination IP per stream
# from the address range above. Zeros arriving on the wire mean a rewrite did
# not happen.

SOURCE_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x01]
DESTINATION_MAC = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

SOURCE_IP = [192, 168, 1, 1]
DESTINATION_IP = [0, 0, 0, 0]

SOURCE_PORT = 50081
DESTINATION_PORT = 50083

# Used only by make_packet.make_packet(), which builds the single original
# stream. The streams above each carry their own size.
FRAME_SIZE = 1518
