# Variable Configuration for P4TG-Mini

# PORTS CONFIGURATION
# PKTGEN PORT: 68, 168
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

# TRAFFIC MIX CONFIGURATION
#
# One entry = one frame size = one packet generator slot.
# The generator cannot change the size of a packet inside a single slot: each
# slot replays one fixed template. A mix of sizes is made by running several
# slots at once, each holding a different size.
#
# "size" is the size on the cable in bytes, including the 4-byte error check.
# "pps" is how many packets per second that size should be sent at.
#
# The share each size gets is simply its pps divided by the total pps. The
# example below is 10% / 10% / 10% / 30% / 30% / 5% / 5%.
#
# At most 16 entries: 8 generator slots per pipe, and there are 2 pipes.
STREAMS = [
    {"size": 64,   "pps": 100_000},
    {"size": 128,  "pps": 100_000},
    {"size": 256,  "pps": 100_000},
    {"size": 512,  "pps": 300_000},
    {"size": 1024, "pps": 300_000},
    {"size": 1280, "pps":  50_000},
    {"size": 1518, "pps":  50_000},
]


# HARDWARE LIMITS
# Generator slots available in one pipe.
MAX_SLOTS_PER_PIPE = 8
# Speed one pipe's generator can produce, in Gbit/s.
PIPE_MAX_GBPS = 100
# Packet memory in one pipe: 1024 rows of 16 bytes.
PKT_BUFFER_BYTES_PER_PIPE = 16384
# Every packet must start on a 16-byte boundary in that memory.
PKT_BUFFER_ALIGNMENT = 16


SOURCE_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x01]
# Placeholder only. The real value is written per port by the switch, from
# PORTS above. Zeros on the wire mean the rewrite did not happen.
DESTINATION_MAC = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

SOURCE_IP = [192, 168, 1, 1]
# Placeholder only, same as above.
DESTINATION_IP = [0, 0, 0, 0]


SOURCE_PORT = 50081
DESTINATION_PORT = 50083
