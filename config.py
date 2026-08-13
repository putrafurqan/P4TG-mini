# Variable Configuration for P4TG-Mini

# PORTS CONFIGURATION
# PKTGEN PORT: 68 (pipe 0), 196 (pipe 1), 324 (pipe 2), 452 (pipe 3) - one per pipe
GENERATOR_PORTS = [68, 196, 324, 452]
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

# GENERATOR SLOT (0-7)
GENERATOR_NUMBER = 0
# Position of the packet in the generator's memory.
MEMORY_POSITION = 0


# THROUGHPUT CONFIGURATION
# Interval between bursts, in nanoseconds.
TIMER_NANOSECONDS = 6152
# Packets produced each interval. One gives the smoothest traffic.
PACKETS_PER_TIMER = 5


# PACKET

# FRAME SIZE IN CABLE: Size on the cable, include 4-bytes error check
FRAME_SIZE = 1518 # Bytes


SOURCE_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x01]
# Placeholder only. The real value is written per port by the switch, from
# PORTS above. Zeros on the wire mean the rewrite did not happen.
DESTINATION_MAC = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

SOURCE_IP = [192, 168, 1, 1]
# Placeholder only, same as above.
DESTINATION_IP = [0, 0, 0, 0]


SOURCE_PORT = 50081
DESTINATION_PORT = 50083
