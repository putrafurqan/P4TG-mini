# Reads the dataplane's own packet and byte counters and prints, for each of
# the 6 output ports, how many packets of each frame size it sent and what
# throughput that works out to.
#
# This is counted on the switch itself, so unlike check_rx.py it does not
# lose packets under load and stays accurate at full rate.
#
# Run it the same way as start.py and stop.py, while traffic is running:
#
#     $SDE/run_bfshell.sh -b monitor.py
#
# SECONDS below is how far apart the two readings are taken. Set RESET_ONLY
# to True to just zero the counter instead, which start.py already does at
# the beginning of every run.

import os
import sys
import time

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

# Same reason as in start.py: bfshell keeps one Python process alive across
# runs, so drop any cached copy of config first.
for module_name in ("config",):
    if module_name in sys.modules:
        del sys.modules[module_name]

import config


SECONDS = 5.0
RESET_ONLY = False

# Must match BUCKETS_PER_PORT and UNCLASSIFIED_BUCKET in p4/p4tg_mini.p4.
BUCKETS_PER_PORT = 32
UNCLASSIFIED_BUCKET = 31

STATS = bfrt.p4tg_mini.pipe.MyEgress.port_size_stats

# bucket_idx -> frame size, numbered the same way start.py numbered them when
# it filled in the classify_size table: order of first appearance in STREAMS.
bucket_size = {}
for stream in config.STREAMS:
    if stream["size"] not in bucket_size.values():
        bucket_size[len(bucket_size)] = stream["size"]


def read_counter():
    """Every index of the counter, as {index: (packets, bytes)}."""

    readings = {}

    entries = STATS.dump(from_hw=True, return_ents=True)
    for entry in entries:
        key = entry.key[b'$COUNTER_INDEX']
        packets = entry.data[b'$COUNTER_SPEC_PKTS']
        byte_count = entry.data[b'$COUNTER_SPEC_BYTES']
        readings[key] = (packets, byte_count)

    return readings


def main():

    if RESET_ONLY:
        STATS.clear()
        print("Monitoring counter cleared.")
        return

    print(f"Measuring for {SECONDS:g} seconds...")

    before = read_counter()
    started = time.time()
    time.sleep(SECONDS)
    after = read_counter()
    elapsed = time.time() - started

    # What changed between the two readings, per (port, size) bucket.
    def change(index):
        old_packets, old_bytes = before.get(index, (0, 0))
        new_packets, new_bytes = after.get(index, (0, 0))
        return new_packets - old_packets, new_bytes - old_bytes

    print()
    print(f"{'port':>10}  {'pps':>13}  {'Gbit/s':>8}  {'packets':>13}")

    port_totals = []

    for port_index, port in enumerate(config.PORTS):
        base = port_index * BUCKETS_PER_PORT

        total_packets = 0
        total_bytes = 0
        per_size = []
        unclassified = 0

        for bucket in range(BUCKETS_PER_PORT):
            packets, byte_count = change(base + bucket)
            if packets == 0:
                continue

            total_packets = total_packets + packets
            total_bytes = total_bytes + byte_count

            if bucket in bucket_size:
                per_size.append((bucket_size[bucket], packets))
            else:
                unclassified = unclassified + packets

        port_totals.append((port, total_packets, per_size, unclassified))

        packets_per_second = total_packets / elapsed
        gigabits = total_bytes * 8 / elapsed / 1000000000

        print(
            f"{port['dev_port']:>10}  {packets_per_second:>13,.0f}  "
            f"{gigabits:>8.3f}  {total_packets:>13,}"
        )

    print()
    print(f"{'port':>10}  {'size':>6}  {'packets':>13}  {'share':>7}")

    for port, total_packets, per_size, unclassified in port_totals:
        if total_packets == 0:
            print(f"{port['dev_port']:>10}  nothing arrived")
            continue

        for size, packets in sorted(per_size):
            share = packets / total_packets * 100
            print(f"{port['dev_port']:>10}  {size:>6}  {packets:>13,}  {share:>6.2f}%")

        if unclassified > 0:
            share = unclassified / total_packets * 100
            print(
                f"{port['dev_port']:>10}  {'?':>6}  {unclassified:>13,}  {share:>6.2f}%"
                "  <- length matches no size in config.py"
            )

    if any(unclassified > 0 for _, _, _, unclassified in port_totals):
        print()
        print("Some packets did not match any configured frame size. The lengths")
        print("the switch sees and the sizes in config.py disagree, most likely by")
        print("a fixed number of bytes. Compare a single-size run against its")
        print("`size` value and adjust the offset in start.py's classify_size step.")


main()
