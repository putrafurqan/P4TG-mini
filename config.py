# Variable Configuration for P4TG-Mini

# PORTS CONFIGURATION
# PKTGEN PORT: 68, 168
GENERATOR_PORT = 68
# FRONT PANEL PORT (188 = FP 1/0)
OUTPUT_PORT = 188
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

DESTINATION_MAC = [0x10, 0x41, 0x6d, 0x18, 0x65, 0xfa]
SOURCE_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x01]

SOURCE_IP = [192, 168, 1, 1]
DESTINATION_IP = [192, 168, 1, 11]

SOURCE_PORT = 50081
DESTINATION_PORT = 50083
