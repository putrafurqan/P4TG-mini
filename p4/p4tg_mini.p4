#include <core.p4>
#include <tna.p4>

const PortId_t GENERATOR_PORT_PIPE_0 = 68;
const PortId_t GENERATOR_PORT_PIPE_1 = 196;



struct my_headers {
    pktgen_timer_header_t generator_header;
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

    table pick_output_port {
        key = {
            ig_intr_md.ingress_port: exact;
        }
        actions = {
            send_to_port;
            send_to_group;
            throw_packet_away;
        }
        const default_action = throw_packet_away();

        size = 8;
    }

    apply {
        if (headers.generator_header.isValid()) {
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

    }
}

typedef bit<48> mac_address;
typedef bit<32> ipv4_address;

header ethernet_h {
    mac_address dst_addr;
    mac_address src_addr;
    bit<16> ether_type;
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

struct my_egress_headers {
    ethernet_h ethernet;
    ipv4_h ipv4;
}

// The 6 output ports, and how many frame-size buckets each one gets. 32
// buckets leaves room for the 16 configured sizes the generator can hold,
// with the top one reserved for lengths that match no configured size.
const int PORT_COUNT = 6;
const int BUCKETS_PER_PORT = 32;
const bit<5> UNCLASSIFIED_BUCKET = 31;

struct my_egress_metadata {
    bit<3> port_idx;    // compact 0-5 index for the 6 output ports
    bit<5> bucket_idx;  // which configured frame size this packet matches
}


parser MyEgressParser(
    packet_in packet,
    out my_egress_headers headers,
    out my_egress_metadata metadata,
    out egress_intrinsic_metadata_t eg_intr_md
) {
    state start {
        packet.extract(eg_intr_md);

        // Give these a definite value up front. The tables below overwrite
        // both for every packet we generate, but a packet that somehow
        // misses them must not index the statistics with whatever happened
        // to be left in the registers.
        metadata.port_idx = 0;
        metadata.bucket_idx = UNCLASSIFIED_BUCKET;

        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(headers.ethernet);
        
        transition select(headers.ethernet.ether_type) {
            0x0800: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(headers.ipv4);

        // UDP and the data after it are left unread and pass through unchanged.
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
    action rewrite_addresses(mac_address new_mac, ipv4_address new_ip, bit<3> port_idx) {
        headers.ethernet.dst_addr = new_mac;
        headers.ipv4.dst_addr = new_ip;
        metadata.port_idx = port_idx;
    }

    table rewrite_per_port {
        key = {
            eg_intr_md.egress_port: exact;
        }
        actions = {
            rewrite_addresses;
            NoAction;
        }
        const default_action = NoAction();

        size = 16;
    }

    // Classifies this copy's wire length against the actual configured
    // frame sizes (at most 16, per the generator's slot limit), so the
    // statistics below can be indexed by which stream a packet belongs to
    // rather than by an arbitrary byte range. A length that matches nothing
    // lands in UNCLASSIFIED_BUCKET, kept separate from the real sizes so it
    // cannot silently inflate one of them.
    action set_bucket(bit<5> bucket_idx) {
        metadata.bucket_idx = bucket_idx;
    }

    table classify_size {
        key = {
            eg_intr_md.pkt_length: exact;
        }
        actions = {
            set_bucket;
        }
        const default_action = set_bucket(UNCLASSIFIED_BUCKET);

        size = 16;
    }

    // Packets and bytes per (port, frame size), flattened:
    // index = port_idx * BUCKETS_PER_PORT + bucket_idx.
    //
    // A Counter is used here rather than a Register because Tofino's stateful
    // ALU -- what a Register compiles down to -- is 32 bits wide, so it cannot
    // add a byte count into a 64-bit value at all, and a 32-bit byte total
    // would wrap in well under a second at these rates. Counters are a separate
    // hardware block that keeps a full 64-bit packet and byte pair and does the
    // byte accounting itself. An indirect counter takes a computed index just
    // like a Register does, so the (port x size) breakdown still works, and the
    // per-port totals are just the sum across that port's buckets.
    Counter<bit<64>, bit<8>>(
        PORT_COUNT * BUCKETS_PER_PORT, CounterType_t.PACKETS_AND_BYTES
    ) port_size_stats;

    apply {
        if (headers.ipv4.isValid()) {
            rewrite_per_port.apply();
            classify_size.apply();

            port_size_stats.count(metadata.port_idx ++ metadata.bucket_idx);
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
        packet.emit(headers);
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
