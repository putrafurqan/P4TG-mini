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


# PACKET PROFILES
# Each profile is a list of flows (app_id, optional pipes, rate, packet
# fields); a flow with no "pipes" is auto-assigned pipes by
# flow_plan.pack_pipes(), and rate is either {"target_pps": N} or
# {"timer_nanosec": T, "packets_per_batch": P}.

PROFILES = {
    "udp_multicast_1514B": {
        "flows": [
            {
                "name": "cbr_1514B",
                "app_id": 0,
                "pipes": [0, 1, 2, 3],
                # Size on the cable, includes 4-byte FCS.
                "frame_size": 1518,  # Bytes
                "ethernet": {
                    "source_mac": [0x02, 0x00, 0x00, 0x00, 0x00, 0x01],
                    # Placeholder, rewritten per port by the switch from PORTS above.
                    "destination_mac": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                },
                "ip": {
                    "source_ip": [192, 168, 1, 1],
                    # Placeholder, rewritten per port by the switch from PORTS above.
                    "destination_ip": [0, 0, 0, 0],
                },
                "udp": {
                    "source_port": 50081,
                    "destination_port": 50083,
                },
                # 5 packets every 6152ns per pipe.
                "rate": {"timer_nanosec": 6152, "packets_per_batch": 5},
            },
        ],
    },
    "IMIX": {
        # Classic 7:4:1 IMIX mix (28/16/4 Mpps); no "pipes" set, so
        # flow_plan.pack_pipes() assigns pipes automatically.
        "flows": [
            {
                "name": "imix_60B",
                "app_id": 0,
                "frame_size": 64,  # 60B named size + 4-byte FCS
                "ethernet": {
                    "source_mac": [0x02, 0x00, 0x00, 0x00, 0x00, 0x01],
                    "destination_mac": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                },
                "ip": {
                    "source_ip": [192, 168, 1, 1],
                    "destination_ip": [0, 0, 0, 0],
                },
                "udp": {
                    "source_port": 50091,
                    "destination_port": 50094,
                },
                # 28 Mpps total, packed automatically across pipes.
                "rate": {"target_pps": 28_000_000},
            },
            {
                "name": "imix_590B",
                "app_id": 1,
                "frame_size": 594,  # 590B named size + 4-byte FCS
                "ethernet": {
                    "source_mac": [0x02, 0x00, 0x00, 0x00, 0x00, 0x01],
                    "destination_mac": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                },
                "ip": {
                    "source_ip": [192, 168, 1, 1],
                    "destination_ip": [0, 0, 0, 0],
                },
                "udp": {
                    "source_port": 50092,
                    "destination_port": 50095,
                },
                # 16 Mpps total, packed automatically across pipes.
                "rate": {"target_pps": 16_000_000},
            },
            {
                "name": "imix_1514B",
                "app_id": 2,
                "frame_size": 1518,  # 1514B named size + 4-byte FCS
                "ethernet": {
                    "source_mac": [0x02, 0x00, 0x00, 0x00, 0x00, 0x01],
                    "destination_mac": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                },
                "ip": {
                    "source_ip": [192, 168, 1, 1],
                    "destination_ip": [0, 0, 0, 0],
                },
                "udp": {
                    "source_port": 50093,
                    "destination_port": 50096,
                },
                # 4 Mpps total, packed automatically across pipes.
                "rate": {"target_pps": 4_000_000},
            },
        ],
    },
}

ACTIVE_PROFILE = "udp_multicast_1514B"


def get_active_profile():
    return PROFILES[ACTIVE_PROFILE]
