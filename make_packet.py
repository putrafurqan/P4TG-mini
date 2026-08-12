import config


ERROR_CHECK_SIZE = 4


def calculate_checksum(header):

    total = 0
    position = 0

    while position < len(header):
        first_byte = header[position]

        # An odd-length message is padded with a zero byte for the purposes of
        # the checksum only. IP headers are always even, but ICMP messages are
        # not.
        if position + 1 < len(header):
            second_byte = header[position + 1]
        else:
            second_byte = 0

        pair = (first_byte * 256) + second_byte

        total = total + pair
        position = position + 2

    while total > 65535:
        extra = total // 65536
        total = (total % 65536) + extra

    checksum = 65535 - total

    return checksum


def make_padding(size):

    data = []

    while len(data) < size:
        data.append(0)

    return data


# LAYERS
#
# Every layer takes the payload it wraps and returns the whole thing. Because it
# receives the payload, len(payload) is exactly the number it needs for its own
# length field, so no offset arithmetic is needed anywhere.
#
# Each call states what follows it, so the chain of EtherTypes and protocol
# numbers is written down rather than implied.


def add_ethernet(payload, destination_mac, source_mac, payload_type):

    header = []

    for number in destination_mac:
        header.append(number)

    for number in source_mac:
        header.append(number)

    header.append(payload_type // 256)
    header.append(payload_type % 256)

    return header + payload


def add_vlan(payload, vlan_id, payload_type):

    # A VLAN tag is the two priority/identifier bytes plus the type of whatever
    # follows. The 0x8100 or 0x88a8 that marks the tag lives in the header
    # before this one, so the caller passes it outward.

    header = []

    header.append(vlan_id // 256)
    header.append(vlan_id % 256)

    header.append(payload_type // 256)
    header.append(payload_type % 256)

    return header + payload


def add_mpls(payload, label, bottom_of_stack, ttl):

    # Label is 20 bits, then 3 bits of traffic class, then the bottom of stack
    # bit, then 8 bits of time to live. Packed into four bytes.

    shim = (label * 4096) + (bottom_of_stack * 256) + ttl

    header = []

    header.append((shim // 16777216) % 256)
    header.append((shim // 65536) % 256)
    header.append((shim // 256) % 256)
    header.append(shim % 256)

    return header + payload


def add_ipv4(payload, source_ip, destination_ip, protocol):

    header = []

    # Version 4, header length 20 bytes.
    header.append(0x45)

    # Priority, unused.
    header.append(0)

    total_length = 20 + len(payload)
    header.append(total_length // 256)
    header.append(total_length % 256)

    # Identification
    header.append(0)
    header.append(0)

    # Fragmentation settings
    header.append(0)
    header.append(0)

    # TTL = 64
    header.append(64)

    header.append(protocol)

    # Checksum, filled in once the rest of the header is complete.
    header.append(0)
    header.append(0)

    for number in source_ip:
        header.append(number)

    for number in destination_ip:
        header.append(number)

    # Positions 10 and 11 are the two checksum bytes.
    checksum = calculate_checksum(header)
    header[10] = checksum // 256
    header[11] = checksum % 256

    return header + payload


def add_ipv6(payload, source_ip, destination_ip, next_header):

    header = []

    # Version 6, no traffic class, no flow label.
    header.append(0x60)
    header.append(0)
    header.append(0)
    header.append(0)

    # Payload length. Unlike IPv4 this counts only what comes after the header.
    payload_length = len(payload)
    header.append(payload_length // 256)
    header.append(payload_length % 256)

    header.append(next_header)

    # Hop limit = 64
    header.append(64)

    for number in source_ip:
        header.append(number)

    for number in destination_ip:
        header.append(number)

    # IPv6 has no header checksum, so there is nothing to fill in afterwards.

    return header + payload


def add_udp(payload, source_port, destination_port):

    header = []

    header.append(source_port // 256)
    header.append(source_port % 256)

    header.append(destination_port // 256)
    header.append(destination_port % 256)

    length = 8 + len(payload)
    header.append(length // 256)
    header.append(length % 256)

    # Checksum switched off. This is allowed over IPv4. Over IPv6 the standard
    # asks for a real checksum, so a receiver that verifies it will complain
    # about the IPv6 stacks. Nothing on the loopback rig verifies it, and the
    # switch does not recalculate it.
    header.append(0)
    header.append(0)

    return header + payload


def add_tcp(payload, source_port, destination_port):

    header = []

    header.append(source_port // 256)
    header.append(source_port % 256)

    header.append(destination_port // 256)
    header.append(destination_port % 256)

    # Sequence number
    header.append(0)
    header.append(0)
    header.append(0)
    header.append(0)

    # Acknowledgement number
    header.append(0)
    header.append(0)
    header.append(0)
    header.append(0)

    # Header length 20 bytes, no options.
    header.append(0x50)

    # Flags: acknowledgement and push set, so this reads as mid-stream data
    # rather than a connection attempt.
    header.append(0x18)

    # Window
    header.append(0xFF)
    header.append(0xFF)

    # Checksum switched off, same reasoning as UDP.
    header.append(0)
    header.append(0)

    # Urgent pointer
    header.append(0)
    header.append(0)

    return header + payload


def add_gre(payload, payload_type):

    header = []

    # No optional fields present, version 0.
    header.append(0)
    header.append(0)

    header.append(payload_type // 256)
    header.append(payload_type % 256)

    return header + payload


def add_vxlan(payload, network_identifier):

    header = []

    # Only the identifier-present flag is set.
    header.append(0x08)
    header.append(0)
    header.append(0)
    header.append(0)

    # 24 bit network identifier, then one reserved byte.
    header.append((network_identifier // 65536) % 256)
    header.append((network_identifier // 256) % 256)
    header.append(network_identifier % 256)
    header.append(0)

    return header + payload


def add_geneve(payload, network_identifier, payload_type):

    header = []

    # Version 0, no options, so the option length is zero.
    header.append(0)

    # No flags set.
    header.append(0)

    header.append(payload_type // 256)
    header.append(payload_type % 256)

    # 24 bit network identifier, then one reserved byte.
    header.append((network_identifier // 65536) % 256)
    header.append((network_identifier // 256) % 256)
    header.append(network_identifier % 256)
    header.append(0)

    return header + payload


def add_gtpu(payload, tunnel_identifier):

    header = []

    # Version 1, GTP protocol, no optional fields.
    header.append(0x30)

    # Message type 255 is user data.
    header.append(0xFF)

    length = len(payload)
    header.append(length // 256)
    header.append(length % 256)

    header.append((tunnel_identifier // 16777216) % 256)
    header.append((tunnel_identifier // 65536) % 256)
    header.append((tunnel_identifier // 256) % 256)
    header.append(tunnel_identifier % 256)

    return header + payload


def add_esp(payload, security_parameters_index, sequence_number):

    # Only the ESP header is built. A real encrypted packet also carries a
    # trailer and an integrity value at the end, which a receiver needs but
    # nothing here checks. Everything after these eight bytes is opaque.

    header = []

    header.append((security_parameters_index // 16777216) % 256)
    header.append((security_parameters_index // 65536) % 256)
    header.append((security_parameters_index // 256) % 256)
    header.append(security_parameters_index % 256)

    header.append((sequence_number // 16777216) % 256)
    header.append((sequence_number // 65536) % 256)
    header.append((sequence_number // 256) % 256)
    header.append(sequence_number % 256)

    return header + payload


def add_segment_routing(payload, segment, next_header):

    # An IPv6 routing extension header of type 4, carrying one segment.
    # Eight bytes of header plus one 16 byte address is 24 bytes, which is
    # three 8 byte units, so the length field is two.

    header = []

    header.append(next_header)
    header.append(2)

    # Routing type 4 is segment routing.
    header.append(4)

    # One segment remains to be visited.
    header.append(1)

    # The segment list holds one entry, at index zero.
    header.append(0)

    # No flags set.
    header.append(0)

    # Tag
    header.append(0)
    header.append(0)

    for number in segment:
        header.append(number)

    return header + payload


def add_icmp_echo(payload, identifier, sequence):

    header = []

    # Type 8 is an echo request, code 0.
    header.append(8)
    header.append(0)

    # Checksum, filled in once the rest of the message is complete.
    header.append(0)
    header.append(0)

    header.append(identifier // 256)
    header.append(identifier % 256)

    header.append(sequence // 256)
    header.append(sequence % 256)

    # Unlike UDP and TCP this checksum covers the whole message and has no
    # pseudo header, so it can be computed here and be correct.
    message = header + payload
    checksum = calculate_checksum(message)
    message[2] = checksum // 256
    message[3] = checksum % 256

    return message


# ADDRESSES USED BY THE STACKS
#
# The outer destination MAC and outer destination IP are placeholders. The
# switch writes the real values per port, from the PORTS list in config.py.
# Zeros arriving on the wire mean the rewrite did not happen.
#
# Inner addresses are never rewritten, because the switch stops parsing at the
# first IP header, so they are set to real values here.

INNER_SOURCE_IP = [172, 16, 0, 1]
INNER_DESTINATION_IP = [172, 16, 0, 2]

SOURCE_IPV6 = [0x20, 0x01, 0x0D, 0xE3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
DESTINATION_IPV6 = [0x20, 0x01, 0x0D, 0xE3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]

INNER_SOURCE_IPV6 = [0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
INNER_DESTINATION_IPV6 = [0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]

SEGMENT = [0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0x01]

# The inner Ethernet header of a bridged tunnel is part of the payload as far as
# the switch is concerned, so it keeps its own fixed addresses.
INNER_DESTINATION_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x11]
INNER_SOURCE_MAC = [0x02, 0x00, 0x00, 0x00, 0x00, 0x12]

TYPE_IPV4 = 0x0800
TYPE_IPV6 = 0x86DD
TYPE_VLAN = 0x8100
TYPE_VLAN_OUTER = 0x88A8
TYPE_MPLS = 0x8847
TYPE_ETHERNET_BRIDGED = 0x6558

PROTOCOL_ICMP = 1
PROTOCOL_TCP = 6
PROTOCOL_UDP = 17
PROTOCOL_GRE = 47
PROTOCOL_ESP = 50
PROTOCOL_ROUTING = 43
PROTOCOL_IPV6 = 41

# IPv6 says "nothing follows this header" with next header 59. A stack that ends
# at IPv6 must say so, otherwise a receiver walks into the padding looking for a
# header that was never built.
PROTOCOL_NO_NEXT_HEADER = 59


# STACKS
#
# One function per stack. Written inside out, so the last line is the outermost
# header. Each takes the number of padding bytes to place at the very centre and
# returns the complete frame without its error check.


def build_ipv4_udp(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, config.SOURCE_PORT, config.DESTINATION_PORT)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_ipv4_tcp(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 80)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_TCP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_vlan_ipv4_udp(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, config.SOURCE_PORT, config.DESTINATION_PORT)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)
    packet = add_vlan(packet, 369, TYPE_IPV4)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_VLAN)

    return packet


def build_qinq_ipv4_tcp(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 80)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_TCP)

    # Inner tag first, then the outer one that carries it.
    packet = add_vlan(packet, 100, TYPE_IPV4)
    packet = add_vlan(packet, 369, TYPE_VLAN)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_VLAN_OUTER)

    return packet


def build_mpls_ipv4_udp(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, config.SOURCE_PORT, config.DESTINATION_PORT)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)

    # A single label is by definition the bottom of the stack.
    packet = add_mpls(packet, 100, 1, 64)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_MPLS)

    return packet


def build_mpls_stack_ipv4_udp(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, config.SOURCE_PORT, config.DESTINATION_PORT)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)

    # The bottom of stack bit is set on the innermost label only.
    packet = add_mpls(packet, 200, 1, 64)
    packet = add_mpls(packet, 100, 0, 64)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_MPLS)

    return packet


def build_ipv6_udp(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, config.SOURCE_PORT, config.DESTINATION_PORT)
    packet = add_ipv6(packet, SOURCE_IPV6, DESTINATION_IPV6, PROTOCOL_UDP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV6)

    return packet


def build_ipv6_tcp(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 443)
    packet = add_ipv6(packet, SOURCE_IPV6, DESTINATION_IPV6, PROTOCOL_TCP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV6)

    return packet


def build_gre_ipv4_tcp(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 80)
    packet = add_ipv4(packet, INNER_SOURCE_IP, INNER_DESTINATION_IP, PROTOCOL_TCP)
    packet = add_gre(packet, TYPE_IPV4)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_GRE)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_gre_bridged(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 80)
    packet = add_ipv4(packet, INNER_SOURCE_IP, INNER_DESTINATION_IP, PROTOCOL_TCP)
    packet = add_ethernet(packet, INNER_DESTINATION_MAC, INNER_SOURCE_MAC, TYPE_IPV4)

    # Transparent Ethernet bridging carries a whole frame inside GRE.
    packet = add_gre(packet, TYPE_ETHERNET_BRIDGED)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_GRE)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_vxlan(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 80)
    packet = add_ipv4(packet, INNER_SOURCE_IP, INNER_DESTINATION_IP, PROTOCOL_TCP)
    packet = add_ethernet(packet, INNER_DESTINATION_MAC, INNER_SOURCE_MAC, TYPE_IPV4)
    packet = add_vxlan(packet, 1000)
    packet = add_udp(packet, 33000, 4789)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_geneve(data_size):

    packet = make_padding(data_size)

    # This stack deliberately stops at IPv6 with no layer 4, which is the one
    # parser case none of the other fifteen cover.
    packet = add_ipv6(packet, INNER_SOURCE_IPV6, INNER_DESTINATION_IPV6,
                      PROTOCOL_NO_NEXT_HEADER)
    packet = add_ethernet(packet, INNER_DESTINATION_MAC, INNER_SOURCE_MAC, TYPE_IPV6)
    packet = add_geneve(packet, 500, TYPE_ETHERNET_BRIDGED)
    packet = add_udp(packet, 33001, 6081)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_gtpu(data_size):

    packet = make_padding(data_size)
    packet = add_udp(packet, 4000, 5000)
    packet = add_ipv4(packet, INNER_SOURCE_IP, INNER_DESTINATION_IP, PROTOCOL_UDP)
    packet = add_gtpu(packet, 0xABCD1234)
    packet = add_udp(packet, 2152, 2152)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_UDP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_esp(data_size):

    packet = make_padding(data_size)
    packet = add_esp(packet, 0x1001, 1)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_ESP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


def build_segment_routing(data_size):

    packet = make_padding(data_size)
    packet = add_tcp(packet, 34567, 179)
    packet = add_ipv6(packet, INNER_SOURCE_IPV6, INNER_DESTINATION_IPV6, PROTOCOL_TCP)

    # The routing header sits between the outer IPv6 header and what it carries,
    # which here is a whole second IPv6 packet.
    packet = add_segment_routing(packet, SEGMENT, PROTOCOL_IPV6)
    packet = add_ipv6(packet, SOURCE_IPV6, DESTINATION_IPV6, PROTOCOL_ROUTING)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV6)

    return packet


def build_icmp(data_size):

    packet = make_padding(data_size)
    packet = add_icmp_echo(packet, 0x1234, 1)
    packet = add_ipv4(packet, config.SOURCE_IP, config.DESTINATION_IP, PROTOCOL_ICMP)
    packet = add_ethernet(packet, config.DESTINATION_MAC, config.SOURCE_MAC, TYPE_IPV4)

    return packet


# Selected by name from the STREAMS list in config.py.
BUILDERS = {
    "ipv4_udp": build_ipv4_udp,
    "ipv4_tcp": build_ipv4_tcp,
    "vlan_ipv4_udp": build_vlan_ipv4_udp,
    "qinq_ipv4_tcp": build_qinq_ipv4_tcp,
    "mpls_ipv4_udp": build_mpls_ipv4_udp,
    "mpls_stack_ipv4_udp": build_mpls_stack_ipv4_udp,
    "ipv6_udp": build_ipv6_udp,
    "ipv6_tcp": build_ipv6_tcp,
    "gre_ipv4_tcp": build_gre_ipv4_tcp,
    "gre_bridged": build_gre_bridged,
    "vxlan": build_vxlan,
    "geneve": build_geneve,
    "gtpu": build_gtpu,
    "esp": build_esp,
    "segment_routing": build_segment_routing,
    "icmp": build_icmp,
}


def build_packet(builder_name, frame_size):

    # The stack is built twice. The first build carries no padding and reveals
    # how big its headers are; the second uses whatever room is left. This stays
    # correct no matter how many layers a stack has.

    if builder_name not in BUILDERS:
        raise ValueError(f"No stack named {builder_name}. Known stacks: {sorted(BUILDERS)}")

    builder = BUILDERS[builder_name]

    headers_only = builder(0)
    data_size = frame_size - ERROR_CHECK_SIZE - len(headers_only)

    if data_size < 0:
        raise ValueError(
            f"Stack {builder_name} needs {smallest_frame(builder_name)} bytes "
            f"on the cable, but frame_size is only {frame_size}."
        )

    # Ethernet does not allow a frame below 64 bytes including the error check.
    # A card or switch that receives one treats it as a runt and discards it.
    if frame_size < 64:
        raise ValueError(f"frame_size {frame_size} is below the Ethernet minimum of 64.")

    return builder(data_size)


def smallest_frame(builder_name):

    # The smallest frame_size this stack can be asked for: its own headers, the
    # error check, and never less than the Ethernet minimum.

    header_size = len(BUILDERS[builder_name](0))

    return max(header_size + ERROR_CHECK_SIZE, 64)


def make_packet():

    # Kept so a single stream still works the way it did before the stacks were
    # added.

    return build_packet("ipv4_udp", config.FRAME_SIZE)


def show(packet, count):

    line = ""

    for position in range(min(count, len(packet))):
        line = line + f"{packet[position]:02x} "

    return line.strip()


if __name__ == "__main__":

    # Checks every stack off the switch, so a mistake here cannot be mistaken
    # for a hardware problem later.

    print(f"{'stack':<22}{'headers':<10}{'at 1518':<10}smallest frame that fits")
    print("-" * 76)

    failures = []

    for name in BUILDERS:
        header_size = len(BUILDERS[name](0))

        packet = build_packet(name, 1518)

        if len(packet) != 1518 - ERROR_CHECK_SIZE:
            failures.append(f"{name} built {len(packet)} bytes, expected {1518 - ERROR_CHECK_SIZE}")

        # Every stack must also build at its own smallest size, which is where
        # an off-by-one in a length field shows up.
        smallest = smallest_frame(name)
        small_packet = build_packet(name, smallest)

        if len(small_packet) != smallest - ERROR_CHECK_SIZE:
            failures.append(f"{name} at its smallest built {len(small_packet)}, expected {smallest - ERROR_CHECK_SIZE}")

        print(f"{name:<22}{header_size:<10}{len(packet):<10}{smallest}")

    print()

    for name in BUILDERS:
        packet = build_packet(name, max(256, smallest_frame(name)))
        print(f"{name}")
        print(f"  {show(packet, 48)}")

    print()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
    else:
        print(f"All {len(BUILDERS)} stacks built correctly.")
