# Counts the frame sizes arriving on one of the receiving NICs and compares
# them with the mix asked for in config.py.
#
# Run this on the switch's Linux side, as root:
#
#     sudo python3 check_rx.py eth1 10
#
# The last number is how many seconds to listen for.
#
# Frames are counted as they are on the cable, so the 4-byte error check is
# added back on: Linux hands over a 1514-byte frame for a 1518-byte frame.

import collections
import socket
import struct
import sys
import time

import config


ETH_P_IP = 0x0800
SOL_PACKET = 263
PACKET_STATISTICS = 6

ERROR_CHECK_SIZE = 4
ETHERNET_HEADER_SIZE = 14
UDP_PROTOCOL = 17

RECEIVE_BUFFER_BYTES = 64 * 1024 * 1024


def open_socket(interface):
    listener = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_IP))
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECEIVE_BUFFER_BYTES)
    listener.bind((interface, 0))
    listener.settimeout(0.5)
    return listener


def is_our_traffic(frame):
    """True if this is one of our generated UDP packets, not other lab traffic."""

    if len(frame) < ETHERNET_HEADER_SIZE + 20:
        return False

    ip_start = ETHERNET_HEADER_SIZE
    header_words = frame[ip_start] & 0x0F
    header_length = header_words * 4

    if frame[ip_start + 9] != UDP_PROTOCOL:
        return False

    udp_start = ip_start + header_length
    if len(frame) < udp_start + 8:
        return False

    destination_port = (frame[udp_start + 2] << 8) + frame[udp_start + 3]

    return destination_port == config.DESTINATION_PORT


def read_drops(listener):
    """How many frames the kernel threw away. Reading this also resets it."""

    statistics = listener.getsockopt(SOL_PACKET, PACKET_STATISTICS, 8)
    seen, dropped = struct.unpack("II", statistics)
    return seen, dropped


def main():

    if len(sys.argv) < 2:
        print("Usage: sudo python3 check_rx.py <interface> [seconds]")
        return 1

    interface = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

    listener = open_socket(interface)
    read_drops(listener)  # clear whatever was counted before we started

    counts = collections.Counter()
    total_frames = 0
    total_bytes = 0
    other_traffic = 0

    print(f"Listening on {interface} for {seconds:g} seconds...")

    started = time.time()
    deadline = started + seconds

    while time.time() < deadline:
        try:
            frame = listener.recv(16384)
        except socket.timeout:
            continue

        if not is_our_traffic(frame):
            other_traffic = other_traffic + 1
            continue

        size_on_cable = len(frame) + ERROR_CHECK_SIZE

        counts[size_on_cable] = counts[size_on_cable] + 1
        total_frames = total_frames + 1
        total_bytes = total_bytes + size_on_cable

    elapsed = time.time() - started
    seen, dropped = read_drops(listener)
    listener.close()

    if total_frames == 0:
        print("No traffic of ours arrived.")
        print("Check that start.py ran, that the link is up, and that the")
        print("destination MAC for this port in config.py matches this NIC.")
        return 1

    # What config.py asked for.
    wanted_total = 0
    for stream in config.STREAMS:
        wanted_total = wanted_total + stream["pps"]

    wanted_share = {}
    for stream in config.STREAMS:
        size = stream["size"]
        wanted_share[size] = wanted_share.get(size, 0) + stream["pps"] / wanted_total * 100

    print()
    print(f"{'size':>6}  {'frames':>12}  {'measured':>9}  {'asked for':>10}  {'difference':>11}")

    every_size = sorted(set(list(counts.keys()) + list(wanted_share.keys())))
    worst_difference = 0

    for size in every_size:
        measured = counts.get(size, 0) / total_frames * 100
        asked = wanted_share.get(size, 0)
        difference = measured - asked

        if abs(difference) > abs(worst_difference):
            worst_difference = difference

        flag = "" if size in wanted_share else "  <- not in config.py"

        print(
            f"{size:>6}  {counts.get(size, 0):>12,}  {measured:>8.2f}%  "
            f"{asked:>9.2f}%  {difference:>+10.2f}%{flag}"
        )

    average_size = total_bytes / total_frames
    packets_per_second = total_frames / elapsed
    gigabits = total_bytes * 8 / elapsed / 1000000000

    wanted_average = 0
    for stream in config.STREAMS:
        wanted_average = wanted_average + stream["size"] * stream["pps"] / wanted_total

    print()
    print(f"Frames counted:      {total_frames:,} in {elapsed:.1f} s")
    print(f"Average frame size:  {average_size:.1f} bytes (asked for {wanted_average:.1f})")
    print(f"Rate seen here:      {packets_per_second:,.0f} pps, {gigabits:.3f} Gbit/s")
    print(f"Largest difference:  {worst_difference:+.2f} percentage points")

    if other_traffic > 0:
        print(f"Ignored {other_traffic:,} frames that were not ours.")

    if dropped > 0:
        share_dropped = dropped / (seen + dropped) * 100 if (seen + dropped) > 0 else 0
        print()
        print(f"WARNING: the kernel dropped {dropped:,} frames ({share_dropped:.1f}%).")
        print("Big frames and small frames are not dropped equally, so the")
        print("percentages above are no longer trustworthy. Lower the pps values")
        print("in config.py, measure the mix again, then use the NIC counters")
        print("to check the full-speed rate.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
