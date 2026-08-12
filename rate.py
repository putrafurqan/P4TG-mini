# Turns a wanted packets-per-second into the two numbers the packet generator
# actually understands: how many packets to send each time the timer fires, and
# how long the timer waits between those bursts.
#
#     packets per second = packets_per_batch / timer_nanoseconds * 1000000000


# The timer cannot be set shorter than this when a burst is used.
T_MIN_BURST_NS = 30

# The largest burst the hardware accepts.
HW_MAX_BURST = 65536

# The timer field is 32 bits wide.
T_MAX_NS = 2**32 - 1

# How many burst sizes to try before settling for the best one found so far.
SEARCH_WIDTH = 4096

# Once the rate is this close to the wanted one, stop looking for a better fit.
CLOSE_ENOUGH = 0.0001  # 0.01 percent


def solve_rate(packets_per_second):
    """Find the batch size and timer that come closest to the wanted rate.

    Both numbers are whole, so most rates cannot be hit exactly. A small burst
    spreads the packets out most evenly, so the search starts at the smallest
    burst the timer allows and only moves up while that buys real accuracy.

    Returns (packets_per_batch, timer_nanoseconds, rate_actually_achieved).
    """

    if packets_per_second <= 0:
        raise ValueError("Packets per second must be greater than zero.")

    # Below this burst size the timer would be shorter than the hardware allows.
    smallest_batch = 1
    while smallest_batch * 1000000000 / packets_per_second < T_MIN_BURST_NS:
        smallest_batch = smallest_batch + 1
        if smallest_batch >= HW_MAX_BURST:
            break

    best_batch = None
    best_timer = None
    best_error = None

    batch = smallest_batch
    tried = 0

    while batch <= HW_MAX_BURST and tried < SEARCH_WIDTH:

        timer = round(batch * 1000000000 / packets_per_second)

        if timer < T_MIN_BURST_NS:
            timer = T_MIN_BURST_NS
        if timer > T_MAX_NS:
            timer = T_MAX_NS

        achieved = batch / timer * 1000000000
        error = abs(achieved - packets_per_second) / packets_per_second

        if best_error is None or error < best_error:
            best_batch = batch
            best_timer = timer
            best_error = error

            if error <= CLOSE_ENOUGH:
                break

        batch = batch + 1
        tried = tried + 1

    achieved = best_batch / best_timer * 1000000000

    return best_batch, best_timer, achieved


def gigabits_per_second(packets_per_second, frame_size):
    """Speed on the cable. Every frame carries 20 extra bytes of gap and preamble."""

    return packets_per_second * (frame_size + 20) * 8 / 1000000000


if __name__ == "__main__":
    import config

    print(f"{'wanted pps':>14}  {'batch':>6}  {'timer ns':>10}  {'actual pps':>14}  {'error':>8}")

    for stream in config.STREAMS:
        wanted = stream["pps"]
        batch, timer, achieved = solve_rate(wanted)
        error = (achieved - wanted) / wanted * 100

        print(f"{wanted:>14,}  {batch:>6}  {timer:>10,}  {achieved:>14,.1f}  {error:>7.3f}%")
