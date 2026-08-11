#include <core.p4>
#include <tna.p4>

const PortId_t GENERATOR_PORT = 68;

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
            GENERATOR_PORT: read_generator_header;
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

    action throw_packet_away() {
        ig_dprsr_md.drop_ctl = 1;
    }

    table pick_output_port {
        key = {
            ig_intr_md.ingress_port: exact;
        }
        actions = {
            send_to_port;
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

struct my_egress_headers {
}

struct my_egress_metadata {
}


parser MyEgressParser(
    packet_in packet,
    out my_egress_headers headers,
    out my_egress_metadata metadata,
    out egress_intrinsic_metadata_t eg_intr_md
) {
    state start {
        packet.extract(eg_intr_md);

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
    apply {
    }
}


control MyEgressDeparser(
    packet_out packet,
    inout my_egress_headers headers,
    in my_egress_metadata metadata,
    in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md
) {
    apply {
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
