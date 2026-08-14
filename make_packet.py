import struct


ETHERNET_HEADER_SIZE = 14
IP_HEADER_SIZE = 20
UDP_HEADER_SIZE = 8
FRAME_CHECK_SEQUENCE_SIZE = 4


def calculate_ip_checksum(header):

    words = struct.unpack(f">{len(header) // 2}H", header)
    total = sum(words)

    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def build_ethernet_header(flow):

    destination_mac = bytes(flow["ethernet"]["destination_mac"])
    source_mac = bytes(flow["ethernet"]["source_mac"])
    ether_type = struct.pack(">H", 0x0800)  # IPv4

    return destination_mac + source_mac + ether_type


def build_ip_header(flow, payload_size):

    total_length = IP_HEADER_SIZE + UDP_HEADER_SIZE + payload_size
    source_ip = bytes(flow["ip"]["source_ip"])
    destination_ip = bytes(flow["ip"]["destination_ip"])

    header = struct.pack(
        ">BBHHHBBH4s4s",
        0x45,           # version 4, header length 20 bytes
        0,              # DSCP/ECN, unused
        total_length,
        0,              # identification
        0,              # flags + fragment offset
        64,             # TTL
        17,             # protocol = UDP
        0,              # checksum, filled in below
        source_ip,
        destination_ip,
    )

    checksum = calculate_ip_checksum(header)

    # Bytes 10-11 are the checksum field.
    return header[:10] + struct.pack(">H", checksum) + header[12:]


def build_udp_header(flow, payload_size):

    length = UDP_HEADER_SIZE + payload_size

    return struct.pack(
        ">HHHH",
        flow["udp"]["source_port"],
        flow["udp"]["destination_port"],
        length,
        0,  # checksum left at zero, a legal "no checksum" for IPv4/UDP
    )


def make_packet(flow):

    header_size = ETHERNET_HEADER_SIZE + IP_HEADER_SIZE + UDP_HEADER_SIZE
    payload_size = flow["frame_size"] - FRAME_CHECK_SEQUENCE_SIZE - header_size
    payload = bytes(payload_size)  # zero-padded

    return (
        build_ethernet_header(flow)
        + build_ip_header(flow, payload_size)
        + build_udp_header(flow, payload_size)
        + payload
    )


if __name__ == "__main__":
    import config

    test_packet = make_packet(config.PROFILES["udp_multicast_1514B"]["flows"][0])
