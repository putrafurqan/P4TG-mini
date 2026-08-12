import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import make_packet


# The generator reads packets out of a buffer that has to be written in 16 byte
# steps. Two streams whose areas overlap corrupt the tail of the earlier packet,
# which shows up as frames that are malformed now and then rather than always,
# so the allocator below refuses to let it happen.
BUFFER_ALIGNMENT = 16

# How many addresses a range holds, by the mask that describes it. The switch
# writes the bottom of the address in one instruction, and the number of bits it
# writes is fixed when the program is compiled, so only these sizes exist. Adding
# another means adding another pair of actions in p4tg_mini.p4.
RANGE_SIZES = {
    0x0000000F: 16,
    0x000000FF: 256,
    0x0000FFFF: 65536,
}


def bytes_to_number(byte_list):
    number = 0
    for byte in byte_list:
        number = number * 256 + byte
    return number


def address_to_number(address):
    # An IPv4 range is written as four numbers, an IPv6 range as the bottom 32
    # bits on their own.
    if isinstance(address, list):
        return bytes_to_number(address)
    return address


def pipe_local_port(dev_port):
    # A dev_port is the pipe in the high bits and the port within that pipe in
    # the low seven: dev_port = (pipe << 7) | local. The generator wants the
    # local half, so both generator ports come out as 68, one in each pipe.
    # Handing it the full dev_port is rejected as an invalid argument.
    return dev_port % 128


def global_slot(stream):
    # app_id runs 0 to 7 inside each pipe, so pipe 1 is shifted up to give one
    # number from 0 to 15. The switch works the same thing out in MyIngress.
    return stream["pipe"] * 8 + stream["app_id"]


def round_up(value, step):
    if value % step == 0:
        return value
    return value + (step - value % step)


# Step 1: build every packet, and refuse to continue if any of them is wrong

packets = {}
problems = []
seen_slots = {}

for stream in config.STREAMS:
    name = stream["name"]
    slot = global_slot(stream)

    if stream["app_id"] < 0 or stream["app_id"] > 7:
        problems.append(f"{name}: app_id {stream['app_id']} is outside the 0 to 7 the hardware has")

    if stream["pipe"] not in (0, 1):
        problems.append(f"{name}: pipe {stream['pipe']} does not exist on this switch")

    if slot in seen_slots:
        problems.append(f"{name}: pipe/app_id already used by {seen_slots[slot]}")
    seen_slots[slot] = name

    if stream["builder"] not in make_packet.BUILDERS:
        problems.append(f"{name}: no stack named {stream['builder']}")
        continue

    smallest = make_packet.smallest_frame(stream["builder"])
    if stream["frame_size"] < smallest:
        problems.append(
            f"{name}: frame_size {stream['frame_size']} is below {smallest}, "
            f"the smallest frame this stack fits in"
        )
        continue

    # The switch builds each destination as base | (counter & mask). Any bit the
    # mask varies has to be zero in the base, or those addresses can never come
    # out and the range silently covers less than it looks like it does.
    mask = stream["addr_mask"]
    base = address_to_number(stream["addr_base"])

    if base & mask != 0:
        problems.append(
            f"{name}: addr_base 0x{base:08x} already has bits set inside "
            f"addr_mask 0x{mask:08x}, so part of that range can never be reached"
        )

    # The switch only knows a few range sizes, because each one is a separate
    # action in the program.
    if mask not in RANGE_SIZES:
        offered = ", ".join(f"0x{known:08x}" for known in sorted(RANGE_SIZES))
        problems.append(
            f"{name}: addr_mask 0x{mask:08x} is not one the switch has an action "
            f"for. Available: {offered}"
        )

    packets[name] = make_packet.build_packet(stream["builder"], stream["frame_size"])

if problems:
    print("Configuration problems, nothing was started:")
    for problem in problems:
        print(f"  - {problem}")
    raise SystemExit(1)


# Step 2: give every packet its own area of the generator buffer
#
# The buffer is written for all pipes at once, so an offset is reserved across
# every stream rather than per pipe. That costs a little space and removes any
# chance of two streams sharing an area.

offsets = {}
next_offset = 0

for stream in config.STREAMS:
    name = stream["name"]
    next_offset = round_up(next_offset, BUFFER_ALIGNMENT)
    offsets[name] = next_offset
    next_offset = next_offset + len(packets[name])

buffer_used = next_offset


# Step 3: report what this configuration will do before doing it

print(f"{'stream':<22}{'pipe':<6}{'slot':<6}{'bytes':<8}{'offset':<9}{'Gbit/s':<9}stack")
print("-" * 92)

speed_per_pipe = {0: 0.0, 1: 0.0}

for stream in config.STREAMS:
    name = stream["name"]
    frame_size = stream["frame_size"]

    # A frame costs 20 bytes more than its size on the cable: 8 for the preamble
    # and start marker, 12 for the gap before the next one.
    bits_per_packet = (frame_size + 20) * 8
    speed = stream["packets_per_timer"] * bits_per_packet / stream["timer_ns"]
    speed_per_pipe[stream["pipe"]] += speed

    print(
        f"{name:<22}{stream['pipe']:<6}{global_slot(stream):<6}"
        f"{len(packets[name]):<8}{offsets[name]:<9}{speed:<9.2f}{stream['builder']}"
    )

print()
for pipe in (0, 1):
    print(f"Pipe {pipe} total: {speed_per_pipe[pipe]:.2f} Gbit/s")
print(f"Both pipes:   {speed_per_pipe[0] + speed_per_pipe[1]:.2f} Gbit/s")
print(f"Buffer used:  {buffer_used} bytes")
print()
print("Every stream is multicast to all six ports, so each port carries the")
print(f"sum of both pipes, {speed_per_pipe[0] + speed_per_pipe[1]:.2f} Gbit/s.")
print()


# Step 4: enable both packet generators

for generator_port in config.GENERATOR_PORTS:
    bfrt.tf1.pktgen.port_cfg.mod(
        dev_port=generator_port,
        pktgen_enable=True,
    )


# Step 5: copy every packet into the switch

for stream in config.STREAMS:
    name = stream["name"]
    bfrt.tf1.pktgen.pkt_buffer.mod(
        pkt_buffer_offset=offsets[name],
        pkt_buffer_size=len(packets[name]),
        buffer=bytes(packets[name]),
    )


# Step 6: fill the multicast group with the 6 active front panel ports

output_ports = []
for port in config.PORTS:
    output_ports.append(port["dev_port"])

try:
    bfrt.pre.mgid.delete(MGID=config.MULTICAST_GROUP)
except:
    pass
try:
    bfrt.pre.node.delete(MULTICAST_NODE_ID=config.MULTICAST_GROUP)
except:
    pass

bfrt.pre.node.entry(
    MULTICAST_NODE_ID=config.MULTICAST_GROUP,
    MULTICAST_RID=0,
    MULTICAST_LAG_ID=[],
    DEV_PORT=output_ports,
).push()

bfrt.pre.mgid.entry(
    MGID=config.MULTICAST_GROUP,
    MULTICAST_NODE_ID=[config.MULTICAST_GROUP],
    MULTICAST_NODE_L1_XID_VALID=[False],
    MULTICAST_NODE_L1_XID=[0],
).push()


# Step 7: send every slot to the multicast group
#
# The table is keyed on the slot as well as the port, so a stream could be sent
# to one port instead by using add_with_send_to_port here.

for stream in config.STREAMS:
    generator_port = config.GENERATOR_PORTS[stream["pipe"]]

    try:
        bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.delete(
            ingress_port=generator_port,
            app_id=stream["app_id"],
        )
    except:
        pass

    bfrt.p4tg_mini.pipe.MyIngress.pick_output_port.add_with_send_to_group(
        ingress_port=generator_port,
        app_id=stream["app_id"],
        group_id=config.MULTICAST_GROUP,
    )


# Step 8: give each port its own destination MAC
#
# This runs for every stack now, not just IPv4 ones. Without it a frame whose
# EtherType is Q-in-Q or MPLS keeps one shared destination and five of the six
# cards discard it.

for port in config.PORTS:
    try:
        bfrt.p4tg_mini.pipe.MyEgress.rewrite_per_port.delete(
            egress_port=port["dev_port"],
        )
    except:
        pass

    bfrt.p4tg_mini.pipe.MyEgress.rewrite_per_port.add_with_rewrite_mac(
        egress_port=port["dev_port"],
        new_mac=bytes_to_number(port["mac"]),
    )


# Step 9: give each slot its destination address range
#
# Two tables, because the switch needs two stages for this: one lays down the
# base address, the next writes the counter over the bottom of it.

for stream in config.STREAMS:
    slot = global_slot(stream)
    base = address_to_number(stream["addr_base"])
    family = "ipv6" if stream["outer"] == "ipv6" else "ipv4"

    base_table = bfrt.p4tg_mini.pipe.MyEgress.address_base
    vary_table = bfrt.p4tg_mini.pipe.MyEgress.address_vary

    try:
        base_table.delete(slot=slot)
    except:
        pass
    try:
        vary_table.delete(slot=slot)
    except:
        pass

    if family == "ipv6":
        base_table.add_with_set_ipv6_base(slot=slot, base=base)
    else:
        base_table.add_with_set_ipv4_base(slot=slot, base=base)

    # The range size picks the action, because writing part of an address is one
    # instruction only when the compiler knows how many bits to write.
    add_vary = getattr(vary_table, f"add_with_vary_{family}_{RANGE_SIZES[stream['addr_mask']]}")
    add_vary(slot=slot)


# Step 10: start the timer on every slot
#
# app_id only identifies a slot within one pipe, so the pipe has to be named as
# well or pipe 0 and pipe 1 would be given the same packet. If the SDE on this
# box wants the pipe expressed differently, this is the only place to change.

# Each slot is armed on its own, and a failure is reported rather than allowed
# to stop the loop. One run then says which slots the switch accepted and which
# it did not, instead of only ever showing the first thing that went wrong.

started = []
refused = []

for stream in config.STREAMS:
    generator_port = config.GENERATOR_PORTS[stream["pipe"]]
    name = stream["name"]

    try:
        bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
            app_id=stream["app_id"],
            pipe=stream["pipe"],
            app_enable=True,
            pkt_len=len(packets[name]),
            timer_nanosec=stream["timer_ns"],
            packets_per_batch_cfg=stream["packets_per_timer"] - 1,
            batch_count_cfg=0,
            pipe_local_source_port=pipe_local_port(generator_port),
            pkt_buffer_offset=offsets[name],
        )
        started.append(name)
    except Exception as failure:
        refused.append((name, stream, failure))

print(f"Started {len(started)} of {len(config.STREAMS)} streams.")

if refused:
    print()
    print("These slots were refused by the switch:")
    for name, stream, failure in refused:
        print(f"  {name}: pipe {stream['pipe']}, app_id {stream['app_id']}, "
              f"pkt_len {len(packets[name])}, timer {stream['timer_ns']}, "
              f"offset {offsets[name]}, "
              f"source port {pipe_local_port(config.GENERATOR_PORTS[stream['pipe']])}")
        print(f"    {type(failure).__name__}: {failure}")
