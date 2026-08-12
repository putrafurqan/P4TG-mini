#include <core.p4>
#include <tna.p4>

const PortId_t GENERATOR_PORT_PIPE_0 = 68;
const PortId_t GENERATOR_PORT_PIPE_1 = 196;

const bit<16> TYPE_IPV4 = 0x0800;
const bit<16> TYPE_IPV6 = 0x86dd;
const bit<16> TYPE_VLAN = 0x8100;
const bit<16> TYPE_VLAN_OUTER = 0x88a8;
const bit<16> TYPE_MPLS = 0x8847;


// Carries the generator slot number from ingress to egress. The slot is only
// known at ingress, but egress needs it to pick that slot's address range.
//
// app_id runs 0 to 7 within each pipe, so the two pipes would collide. The
// number carried here is offset by the pipe to give one global slot number from
// 0 to 15, which is what the control plane addresses.
header bridged_h {
    bit<8> slot;
}

struct my_headers {
    pktgen_timer_header_t generator_header;
    bridged_h bridged;
}

struct my_metadata {
}

parser MyIngressParser(
    packet_in packet,
    out my_headers headers,
    out my_metadata metadata,
    out ingress_intrinsic_metadata_t ig_intr_md
) {
    state start {
        packet.extract(ig_intr_md);
        packet.advance(PORT_METADATA_SIZE);

        transition select(ig_intr_md.ingress_port) {
            GENERATOR_PORT_PIPE_0: read_generator_header;
            GENERATOR_PORT_PIPE_1: read_generator_header;
            default: accept;
        }
    }

    state read_generator_header {
        packet.extract(headers.generator_header);
        transition accept;
    }
}


control MyIngress(
    inout my_headers headers,
    inout my_metadata metadata,
    in ingress_intrinsic_metadata_t ig_intr_md,
    in ingress_intrinsic_metadata_from_parser_t ig_prsr_md,
    inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
    inout ingress_intrinsic_metadata_for_tm_t ig_tm_md
) {
    action send_to_port(PortId_t port_number) {
        ig_tm_md.ucast_egress_port = port_number;
    }
    action send_to_group(MulticastGroupId_t group_id) {
        ig_tm_md.mcast_grp_a = group_id;
    }

    action throw_packet_away() {
        ig_dprsr_md.drop_ctl = 1;
    }

    // Keyed on the slot as well as the port, so different slots can be sent to
    // different ports or groups rather than all sharing one destination.
    // The @name fixes what the control plane calls this key. Without it the
    // name is derived from the header path and start.py has to guess.
    table pick_output_port {
        key = {
            ig_intr_md.ingress_port: exact;
            headers.generator_header.app_id: exact @name("app_id");
        }
        actions = {
            send_to_port;
            send_to_group;
            throw_packet_away;
        }
        const default_action = throw_packet_away();

        size = 32;
    }

    apply {
        if (headers.generator_header.isValid()) {
            // The generator header itself is never emitted, so it leaves the
            // packet here. Only the slot number is carried forward.
            headers.bridged.setValid();

            if (ig_intr_md.ingress_port == GENERATOR_PORT_PIPE_1) {
                headers.bridged.slot = 8 + (bit<8>) headers.generator_header.app_id;
            } else {
                headers.bridged.slot = (bit<8>) headers.generator_header.app_id;
            }

            pick_output_port.apply();
        } else {
            throw_packet_away();
        }
    }
}


control MyIngressDeparser(
    packet_out packet,
    inout my_headers headers,
    in my_metadata metadata,
    in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md
) {
    apply {
        // The generator header is deliberately not emitted, which is what
        // strips it from the packet.
        packet.emit(headers.bridged);
    }
}

typedef bit<48> mac_address;
typedef bit<32> ipv4_address;

header ethernet_h {
    mac_address dst_addr;
    mac_address src_addr;
    bit<16> ether_type;
}

header vlan_h {
    bit<3>  priority;
    bit<1>  drop_eligible;
    bit<12> vlan_id;
    bit<16> ether_type;
}

header mpls_h {
    bit<20> label;
    bit<3>  traffic_class;
    bit<1>  bottom_of_stack;
    bit<8>  ttl;
}

header ipv4_h {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> total_len;
    bit<16> identification;
    bit<3>  flags;
    bit<13> frag_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdr_checksum;
    ipv4_address src_addr;
    ipv4_address dst_addr;
}

header ipv6_h {
    bit<4>   version;
    bit<8>   traffic_class;
    bit<20>  flow_label;
    bit<16>  payload_len;
    bit<8>   next_header;
    bit<8>   hop_limit;
    bit<128> src_addr;
    bit<128> dst_addr;
}

struct my_egress_headers {
    bridged_h  bridged;
    ethernet_h ethernet;
    vlan_h     vlan_0;
    vlan_h     vlan_1;
    mpls_h     mpls_0;
    mpls_h     mpls_1;
    ipv4_h     ipv4;
    ipv6_h     ipv6;
}

struct my_egress_metadata {
    // Where this packet sits in its slot's address range. Read from the counter
    // in one stage and applied to the address in the next.
    bit<32> offset;
}


// Parses down to the first IP header and stops there, whatever shims precede
// it. Tunnelled inner headers are never parsed: everything past the first IP
// header stays opaque and passes through byte for byte, which is what lets any
// stack be generated without the switch knowing about it.
parser MyEgressParser(
    packet_in packet,
    out my_egress_headers headers,
    out my_egress_metadata metadata,
    out egress_intrinsic_metadata_t eg_intr_md
) {
    state start {
        packet.extract(eg_intr_md);
        packet.extract(headers.bridged);
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(headers.ethernet);

        transition select(headers.ethernet.ether_type) {
            TYPE_VLAN: parse_vlan_0;
            TYPE_VLAN_OUTER: parse_vlan_0;
            TYPE_MPLS: parse_mpls_0;
            TYPE_IPV4: parse_ipv4;
            TYPE_IPV6: parse_ipv6;
            default: accept;
        }
    }

    state parse_vlan_0 {
        packet.extract(headers.vlan_0);

        transition select(headers.vlan_0.ether_type) {
            TYPE_VLAN: parse_vlan_1;
            TYPE_MPLS: parse_mpls_0;
            TYPE_IPV4: parse_ipv4;
            TYPE_IPV6: parse_ipv6;
            default: accept;
        }
    }

    state parse_vlan_1 {
        packet.extract(headers.vlan_1);

        transition select(headers.vlan_1.ether_type) {
            TYPE_MPLS: parse_mpls_0;
            TYPE_IPV4: parse_ipv4;
            TYPE_IPV6: parse_ipv6;
            default: accept;
        }
    }

    state parse_mpls_0 {
        packet.extract(headers.mpls_0);

        transition select(headers.mpls_0.bottom_of_stack) {
            1: parse_after_mpls;
            default: parse_mpls_1;
        }
    }

    // Two labels is the deepest stack any of the generated packets uses. A
    // third would need another state here.
    state parse_mpls_1 {
        packet.extract(headers.mpls_1);
        transition parse_after_mpls;
    }

    state parse_after_mpls {
        // An MPLS payload carries no type field, so the IP version nibble is
        // the only thing that says which header comes next.
        transition select(packet.lookahead<bit<4>>()) {
            4: parse_ipv4;
            6: parse_ipv6;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(headers.ipv4);
        transition accept;
    }

    state parse_ipv6 {
        packet.extract(headers.ipv6);
        transition accept;
    }
}


control MyEgress(
    inout my_egress_headers headers,
    inout my_egress_metadata metadata,
    in egress_intrinsic_metadata_t eg_intr_md,
    in egress_intrinsic_metadata_from_parser_t eg_prsr_md,
    inout egress_intrinsic_metadata_for_deparser_t eg_dprsr_md,
    inout egress_intrinsic_metadata_for_output_port_t eg_oport_md
) {
    // One counter per generator slot, indexed by the global slot number.
    Register<bit<32>, bit<8>>(256) flow_counter;

    RegisterAction<bit<32>, bit<8>, bit<32>>(flow_counter) take_next_offset = {
        void apply(inout bit<32> value, out bit<32> result) {
            value = value + 1;
            result = value;
        }
    };

    // Works for every stack, because Ethernet is always parsed. This is what
    // keeps each port's identity when the stack is not IPv4.
    action rewrite_mac(mac_address new_mac) {
        headers.ethernet.dst_addr = new_mac;
    }

    table rewrite_per_port {
        key = {
            eg_intr_md.egress_port: exact;
        }
        actions = {
            rewrite_mac;
            NoAction;
        }
        const default_action = NoAction();

        size = 16;
    }

    // Walks the destination address through a configured range, one step per
    // packet, wrapping at the end. Unlike a random value this is exhaustive and
    // repeatable, so a receiver can be set up for exactly the range in use and a
    // capture can be checked for full coverage.
    //
    // This takes two stages, because a Tofino action can only produce a value in
    // one operation and "base combined with a masked counter" is two. So the
    // first stage lays down the base address and reads the counter, which is two
    // operations on two different fields and therefore fine, and the second
    // stage writes the counter over the bottom of the address. Writing part of a
    // field is a single instruction, which is why the range size comes from a
    // choice of actions rather than from a mask passed in.

    action set_ipv4_base(ipv4_address base) {
        metadata.offset = take_next_offset.execute(headers.bridged.slot);
        headers.ipv4.dst_addr = base;
    }

    action set_ipv6_base(bit<32> base) {
        metadata.offset = take_next_offset.execute(headers.bridged.slot);
        headers.ipv6.dst_addr[31:0] = base;
    }

    table address_base {
        key = {
            headers.bridged.slot: exact @name("slot");
        }
        actions = {
            set_ipv4_base;
            set_ipv6_base;
            NoAction;
        }
        // A slot with no entry keeps whatever address the builder put in, which
        // is the all zero placeholder. Zeros on the wire mean this table was
        // not populated.
        const default_action = NoAction();

        size = 32;
    }

    // One action per range size. Four bits is 16 addresses, eight is 256,
    // sixteen is 65536. A size not listed here needs another action.
    action vary_ipv4_16()    { headers.ipv4.dst_addr[3:0]  = metadata.offset[3:0]; }
    action vary_ipv4_256()   { headers.ipv4.dst_addr[7:0]  = metadata.offset[7:0]; }
    action vary_ipv4_65536() { headers.ipv4.dst_addr[15:0] = metadata.offset[15:0]; }

    action vary_ipv6_16()    { headers.ipv6.dst_addr[3:0]  = metadata.offset[3:0]; }
    action vary_ipv6_256()   { headers.ipv6.dst_addr[7:0]  = metadata.offset[7:0]; }
    action vary_ipv6_65536() { headers.ipv6.dst_addr[15:0] = metadata.offset[15:0]; }

    table address_vary {
        key = {
            headers.bridged.slot: exact @name("slot");
        }
        actions = {
            vary_ipv4_16;
            vary_ipv4_256;
            vary_ipv4_65536;
            vary_ipv6_16;
            vary_ipv6_256;
            vary_ipv6_65536;
            NoAction;
        }
        // No entry means the address stays at the base, which is a slot with a
        // range of exactly one.
        const default_action = NoAction();

        size = 32;
    }

    apply {
        rewrite_per_port.apply();

        if (headers.ipv4.isValid() || headers.ipv6.isValid()) {
            address_base.apply();
            address_vary.apply();
        }
    }
}


control MyEgressDeparser(
    packet_out packet,
    inout my_egress_headers headers,
    in my_egress_metadata metadata,
    in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md
) {
    Checksum() ipv4_checksum;

    apply {
        if (headers.ipv4.isValid()) {
            headers.ipv4.hdr_checksum = ipv4_checksum.update({
                headers.ipv4.version,
                headers.ipv4.ihl,
                headers.ipv4.diffserv,
                headers.ipv4.total_len,
                headers.ipv4.identification,
                headers.ipv4.flags,
                headers.ipv4.frag_offset,
                headers.ipv4.ttl,
                headers.ipv4.protocol,
                headers.ipv4.src_addr,
                headers.ipv4.dst_addr
            });
        }

        // Emitted one at a time rather than as a struct, so the bridged header
        // is left behind instead of being sent onto the wire. IPv6 has no
        // header checksum, so the address rewrite needs no repair there.
        packet.emit(headers.ethernet);
        packet.emit(headers.vlan_0);
        packet.emit(headers.vlan_1);
        packet.emit(headers.mpls_0);
        packet.emit(headers.mpls_1);
        packet.emit(headers.ipv4);
        packet.emit(headers.ipv6);
    }
}


Pipeline(
    MyIngressParser(),
    MyIngress(),
    MyIngressDeparser(),
    MyEgressParser(),
    MyEgress(),
    MyEgressDeparser()
) pipe;

Switch(pipe) main;
