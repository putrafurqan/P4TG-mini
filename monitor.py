# Reads the dataplane's own packet/byte counters and prints a per-port frame
# size histogram plus measured throughput -- ground truth from the switch
# ASIC, not a lossy userspace capture like check_rx.py.
#
# Run this the same way as start.py/stop.py, via bfshell:
#
#     $SDE/run_bfshell.sh -b monitor.py
#
# Optional: edit SECONDS below to change how long the two snapshots are
# spaced apart, or set RESET_ONLY = True to just zero the registers (the
# same thing start.py's Step 0 does) without taking a measurement.

import time

this_folder = None
try:
    import os
    import sys
    this_folder = os.path.dirname(os.path.abspath(__file__))
    if this_folder not in sys.path:
        sys.path.append(this_folder)
except NameError:
    pass

for module_name in ("config",):
    if module_name in sys.modules:
        del sys.modules[module_name]

import config


SECONDS = 5.0
RESET_ONLY = False

NUM_BUCKETS = 16  # must match `bit<4> bucket_idx` / the classify_size table size in p4tg_mini.p4

port_names = [f"port {port['dev_port']}" for port in config.PORTS]

# bucket_idx -> configured frame size, same numbering start.py used when it
# populated classify_size (order of first appearance in config.STREAMS).
bucket_size = {}
for stream in config.STREAMS:
    if stream["size"] not in bucket_size.values():
        bucket_size[len(bucket_size)] = stream["size"]


def clear_registers():
    for register in (
        bfrt.p4tg_mini.pipe.MyEgress.port_pkt_count,
        bfrt.p4tg_mini.pipe.MyEgress.port_byte_count,
        bfrt.p4tg_mini.pipe.MyEgress.size_histogram,
    ):
        register.clear()


def read_register(register, size, field):
    """Reads every index of a register array from the ASIC into a plain list.

    `field` is the data field name bfrt exposes for this register's value
    (visible via `register.info()` on the box if this needs adjusting --
    it is usually the P4 register's variable name, e.g. "port_pkt_count.f1").
    """
    values = [0] * size
    entries = register.dump(from_hw=True, return_ents=True)
    for entry in entries:
        index = entry.key[b'$REGISTER_INDEX']
        raw = entry.data[field]
        # Tofino registers are per-pipeline-stage; bfrt returns one value per
        # stage as a list and they should all agree once traffic has settled.
        values[index] = raw[0] if isinstance(raw, list) else raw
    return values


def snapshot():
    pkt_count = read_register(
        bfrt.p4tg_mini.pipe.MyEgress.port_pkt_count, len(config.PORTS),
        b'MyEgress.port_pkt_count.f1',
    )
    byte_count = read_register(
        bfrt.p4tg_mini.pipe.MyEgress.port_byte_count, len(config.PORTS),
        b'MyEgress.port_byte_count.f1',
    )
    histogram = read_register(
        bfrt.p4tg_mini.pipe.MyEgress.size_histogram, len(config.PORTS) * NUM_BUCKETS,
        b'MyEgress.size_histogram.f1',
    )
    return pkt_count, byte_count, histogram


def main():
    if RESET_ONLY:
        clear_registers()
        print("Monitoring registers cleared.")
        return

    print(f"Measuring for {SECONDS:g} seconds...")

    pkt_before, byte_before, hist_before = snapshot()
    started = time.time()
    time.sleep(SECONDS)
    pkt_after, byte_after, hist_after = snapshot()
    elapsed = time.time() - started

    print()
    print(f"{'port':>10}  {'pps':>12}  {'Gbit/s':>8}  {'packets':>12}")

    for idx, name in enumerate(port_names):
        pkt_delta = pkt_after[idx] - pkt_before[idx]
        byte_delta = byte_after[idx] - byte_before[idx]

        pps = pkt_delta / elapsed
        gbps = byte_delta * 8 / elapsed / 1_000_000_000

        print(f"{name:>10}  {pps:>12,.0f}  {gbps:>8.3f}  {pkt_delta:>12,}")

    print()
    print(f"{'port':>10}  {'size':>6}  {'packets':>12}")
    for idx, name in enumerate(port_names):
        base = idx * NUM_BUCKETS
        histogram_total = 0
        for bucket, size in sorted(bucket_size.items()):
            count = hist_after[base + bucket] - hist_before[base + bucket]
            histogram_total = histogram_total + count
            if count > 0:
                print(f"{name:>10}  {size:>6}  {count:>12,}")

        unclassified_bucket = max(bucket_size.keys(), default=-1) + 1
        unclassified = 0
        for bucket in range(unclassified_bucket, NUM_BUCKETS):
            unclassified = unclassified + (hist_after[base + bucket] - hist_before[base + bucket])
        if unclassified > 0:
            print(f"{name:>10}  {'?':>6}  {unclassified:>12,}  <- classify_size has no entry for this length")
            histogram_total = histogram_total + unclassified

        pkt_delta = pkt_after[idx] - pkt_before[idx]
        if histogram_total != pkt_delta:
            print(
                f"{name:>10}  WARNING: histogram total ({histogram_total:,}) != "
                f"packet count ({pkt_delta:,})"
            )


main()
