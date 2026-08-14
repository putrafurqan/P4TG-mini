import math

import config
import make_packet


# Per-pipe capacity ceiling used by the packer below.
PIPE_CAPACITY_GBIT = 100.0
NUM_PIPES = len(config.GENERATOR_PORTS)


def flow_total_gbit(flow):
    bits_per_wire_packet = (flow["frame_size"] + 20) * 8
    return flow["rate"]["target_pps"] * bits_per_wire_packet / 1_000_000_000


def pack_pipes(flows):
    """Assigns each target_pps flow (skipping flows with an explicit
    "pipes" list) to the minimum number of unclaimed pipes needed to keep
    its per-pipe share under PIPE_CAPACITY_GBIT."""

    assigned_pipes = {}
    next_pipe = 0

    for flow in flows:
        if "pipes" in flow:
            continue

        num_pipes_needed = max(1, math.ceil(flow_total_gbit(flow) / PIPE_CAPACITY_GBIT))

        if next_pipe + num_pipes_needed > NUM_PIPES:
            raise ValueError(
                f"Flow '{flow['name']}' needs {num_pipes_needed} pipe(s) "
                f"({flow_total_gbit(flow):.2f} Gbit/s) but only "
                f"{NUM_PIPES - next_pipe} pipe(s) are left unassigned."
            )

        assigned_pipes[flow["name"]] = list(range(next_pipe, next_pipe + num_pipes_needed))
        next_pipe += num_pipes_needed

    return assigned_pipes


# Target trigger period used when solving batch size for a pps target.
REFERENCE_PERIOD_NANOSECONDS = 6152

# Minimum/aligned size pktgen buffer writes must satisfy; pkt_len (what
# actually gets replayed) still uses the true, unpadded packet length.
BUFFER_WRITE_ALIGNMENT = 16
BUFFER_WRITE_MIN_SIZE = 64


def pad_for_buffer_write(packet):
    aligned_size = -(-len(packet) // BUFFER_WRITE_ALIGNMENT) * BUFFER_WRITE_ALIGNMENT
    padded_size = max(BUFFER_WRITE_MIN_SIZE, aligned_size)
    return packet + bytes(padded_size - len(packet))


def resolve_rate(rate, num_pipes):

    if "target_pps" in rate:
        per_pipe_pps = rate["target_pps"] / num_pipes
        # Solve integer batch size and timer period for the target rate.
        packets_per_batch = max(1, round(per_pipe_pps * REFERENCE_PERIOD_NANOSECONDS / 1_000_000_000))
        timer_nanosec = round(packets_per_batch / per_pipe_pps * 1_000_000_000)
        packets_per_batch_cfg = packets_per_batch - 1
    else:
        timer_nanosec = rate["timer_nanosec"]
        packets_per_batch_cfg = rate["packets_per_batch"] - 1

    return timer_nanosec, packets_per_batch_cfg


def build_flow_plan(profile):
    """One entry per (flow, pipe); buffer offsets are packed back-to-back per flow."""

    plan = []
    offset = 0
    packed_pipes = pack_pipes(profile["flows"])

    for flow in profile["flows"]:
        packet = make_packet.make_packet(flow)
        buffer_bytes = pad_for_buffer_write(packet)
        pipes = flow.get("pipes", packed_pipes.get(flow["name"]))
        timer_nanosec, packets_per_batch_cfg = resolve_rate(flow["rate"], len(pipes))

        for pipe in pipes:
            dev_port = config.GENERATOR_PORTS[pipe]
            plan.append({
                "flow_name": flow["name"],
                "app_id": flow["app_id"],
                "pipe": pipe,
                "dev_port": dev_port,
                "local_port": dev_port % 128,
                "packet": packet,              # true bytes, drives pkt_len
                "buffer_bytes": buffer_bytes,  # padded bytes, drives the pkt_buffer.mod write
                "pkt_buffer_offset": offset,
                "timer_nanosec": timer_nanosec,
                "packets_per_batch_cfg": packets_per_batch_cfg,
            })

        offset += len(buffer_bytes)

    return plan
