## What it does

Generates a mix of sixteen different packet stacks at once, from the switch's own
packet generator. The point is coverage: a device under test sees Q-in-Q, MPLS
label stacks, GRE, VXLAN, GENEVE, GTP-U, ESP, segment routing, IPv4 and IPv6, all
in the same session, instead of one repeated frame.

Sixteen is the hardware ceiling, not a design choice: the Tofino 1 in this rig has
**two pipes with eight generator slots each**. A seventeenth stack needs a second
session.

Nothing in the switch program understands any of these stacks. It parses down to
the first IP header and stops, so everything past that is opaque bytes that pass
through untouched. That is why any stack can be added by writing bytes in Python,
with no change to the P4.

## Using it

**1. Check the packets without the switch.** Runs anywhere, needs nothing
installed.

```bash
python3 make_packet.py
```

Every stack is built at full size and at its own smallest size, and the lengths
are checked. A mistake caught here cannot be mistaken for a hardware fault later.

**2. Put the program on the switch.**

```bash
/opt/barefoot/tools/p4_build.sh ~/exp/P4TG-mini/p4/p4tg_mini.p4
```

```bash
$SDE/run_switchd.sh -p p4tg_mini
```

**3. Start the traffic.**

```bash
$SDE/run_bfshell.sh -b ~/exp/P4TG-mini/start.py
```

It prints what it is about to do first: every stream with its slot, size, buffer
offset and rate, then the per pipe totals. If anything is wrong with the
configuration it says so and starts nothing.

**4. Stop the traffic.**

```bash
$SDE/run_bfshell.sh -b ~/exp/P4TG-mini/stop.py
```

Stops all sixteen slots on both pipes, including any left armed by an earlier run
with a different configuration.

**5. Confirm it on the wire.**

```bash
sudo tcpdump -i eth1 -e -nn -c 200
```

Every stream is multicast to all six ports, so one capture shows all sixteen
stacks. What to look for:

- each stack decodes with its full layering, tags, labels and tunnel identifiers
- each port shows **its own** destination MAC, including on the MPLS and Q-in-Q
  frames, which is the thing that used to be broken
- destination addresses walk their range and wrap round
- frame sizes differ per stream, matching the table start.py printed

## Configuration

Everything is in the `STREAMS` list in `config.py`, one entry per slot:

```python
{"name": "vxlan", "pipe": 1, "app_id": 2, "builder": "vxlan",
 "frame_size": 1518, "timer_ns": 6152, "packets_per_timer": 1,
 "outer": "ipv4", "addr_base": [10, 2, 0, 0], "addr_mask": 0x0000FFFF},
```

**Rate.** One size per slot; the hardware cannot vary it per packet.

```
speed in Gbit/s  =  packets_per_timer * (frame_size + 20) * 8  /  timer_ns
```

Examples at 1518 bytes:

| timer_ns | packets_per_timer | Speed |
|---|---|---|
| 12304 | 1 | 1 Gbit/s |
| 6152 | 1 | 2 Gbit/s |
| 6152 | 5 | 10 Gbit/s |
| 3076 | 25 | 100 Gbit/s |

All slots on one pipe share that pipe's generator, and every stream is multicast
to six ports, so each port carries the sum of all sixteen. Add the rates up before
raising them.

**Address ranges.** Each slot walks its destination address through a range, one
step per packet, wrapping at the end. `addr_mask` sets the size, and only three
values exist:

| addr_mask | Addresses |
|---|---|
| `0x0000000F` | 16 |
| `0x000000FF` | 256 |
| `0x0000FFFF` | 65536 |

The list is short for a hardware reason. The switch writes the counter over the
bottom of the address, and writing part of a field is only a single instruction
when the number of bits is fixed at compile time, so each size is a separate
action in `p4tg_mini.p4`. Another size means another pair of actions there and
another line in `RANGE_SIZES` in `start.py`.

`addr_base` must have zeros in the bits the counter overwrites, or those bits are
just discarded; `start.py` refuses to start if a mask is not one of the three.

The walk is deliberate rather than random: it is repeatable, and it covers every
address exactly once per lap, so a receiver can be set up for exactly the range in
use and a capture can be checked for full coverage.

**Adding a stack.** Write a `build_<name>()` in `make_packet.py` from the layer
functions already there, add it to `BUILDERS`, and point a `STREAMS` entry at it.
No P4 change is needed unless the new stack puts something before the first IP
header that the egress parser does not yet know about — currently VLAN tags (two
deep) and MPLS labels (two deep).

## What it cannot do

Limits of a hardware packet generator, not of this program:

- **No stateful traffic.** No handshakes, no sessions, nothing responds. A TCP or
  TLS header can be emitted but it is a snapshot, not a conversation.
- **No per packet size variation.** One size per slot. An IMIX is approximated
  with several slots at different sizes and weighted rates.
- **No capture replay**, and **no receive path** at all.
