import config


ETHERNET_HEADER_SIZE = 14
IP_HEADER_SIZE = 20
UDP_HEADER_SIZE = 8
ERROR_CHECK_SIZE = 4


def calculate_checksum(header):

    total = 0
    position = 0
    
    while position < len(header):
        first_byte = header[position]
        second_byte = header[position + 1]

        pair = (first_byte * 256) + second_byte

        total = total + pair
        position = position + 2

    while total > 65535:
        extra = total // 65536
        total = (total % 65536) + extra

    checksum = 65535 - total

    return checksum


def make_packet():

    packet = []

    for number in config.DESTINATION_MAC:
        packet.append(number)

    for number in config.SOURCE_MAC:
        packet.append(number)

    # Packet Type = 0x800 (IP Packet)
    packet.append(0x08)
    packet.append(0x00)

    space_for_headers = ETHERNET_HEADER_SIZE + IP_HEADER_SIZE + UDP_HEADER_SIZE
    data_size = config.FRAME_SIZE - ERROR_CHECK_SIZE - space_for_headers

    ip_header = []

    # Version 4, header length 20 bytes.
    ip_header.append(0x45)

    # Priority, unused.
    ip_header.append(0)

    # Length of the IP header, UDP header and data. A 16 bit value, so it is split across two bytes.
    ip_length = IP_HEADER_SIZE + UDP_HEADER_SIZE + data_size
    ip_header.append(ip_length // 256)
    ip_header.append(ip_length % 256)

    # Identification
    ip_header.append(0)
    ip_header.append(0)

    # Fragmentation Settings
    ip_header.append(0)
    ip_header.append(0)

    # TTL = 64
    ip_header.append(64)

    # L4 Protcol = UDP
    ip_header.append(17)

    # Checksum, filled in once the rest of the header is complete.
    ip_header.append(0)
    ip_header.append(0)

    for number in config.SOURCE_IP:
        ip_header.append(number)

    for number in config.DESTINATION_IP:
        ip_header.append(number)

    # Positions 10 and 11 are the two checksum bytes.
    checksum = calculate_checksum(ip_header)
    ip_header[10] = checksum // 256
    ip_header[11] = checksum % 256

    for number in ip_header:
        packet.append(number)

    # UDP HEADER

    packet.append(config.SOURCE_PORT // 256)
    packet.append(config.SOURCE_PORT % 256)

    packet.append(config.DESTINATION_PORT // 256)
    packet.append(config.DESTINATION_PORT % 256)

    udp_length = UDP_HEADER_SIZE + data_size
    packet.append(udp_length // 256)
    packet.append(udp_length % 256)

    # UDP CHECKSUM ZERO
    packet.append(0)
    packet.append(0)

    # DATA
    # Padded with zeros until the requested size is reached.

    while len(packet) < config.FRAME_SIZE - ERROR_CHECK_SIZE:
        packet.append(0)

    return packet

if __name__ == "__main__":
    test_packet = make_packet()