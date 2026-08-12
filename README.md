## Using it

**1. Put the program on the switch.** 

```bash
/opt/barefoot/tools/p4_build.sh ~/exp/P4TG-mini/p4/p4tg_mini.p4
```

```bash
$SDE/run_switchd.sh -p p4tg_mini
```

**2. Start the traffic.**

```bash
$SDE/run_bfshell.sh -b ~/exp/P4TG-mini/start.py
```

**3. Stop the traffic.**

```bash
$SDE/run_bfshell.sh -b ~/exp/P4TG-mini/stop.py
```

## Frame sizes and throughput

At `config.py`. One entry per frame size, each with its own rate:

```python
STREAMS = [
    {"size": 64,   "pps": 100_000},
    {"size": 128,  "pps": 100_000},
    {"size": 256,  "pps": 100_000},
    {"size": 512,  "pps": 300_000},
    {"size": 1024, "pps": 300_000},
    {"size": 1280, "pps":  50_000},
    {"size": 1518, "pps":  50_000},
]
```

`size` is the size on the cable in bytes, including the 4-byte error check.
`pps` is packets per second for that size.

The share each size gets is its `pps` divided by the total. The list above is
10% / 10% / 10% / 30% / 30% / 5% / 5%. To send a single size, use a list of one
entry.

```
speed in Gbit/s  =  pps * (size + 20) * 8 / 1000000000
```

`start.py` turns each `pps` into the burst size and timer the hardware wants,
then prints what it set up, including the achieved rate and the real share of
each size. Run `python rate.py` on its own to see that table without touching
the switch.

### Limits

- **16 frame sizes at most.** The generator has 8 slots per pipe and there are
  2 pipes. Slots are filled on pipe 0 first, then pipe 1.
- **100 Gbit/s per pipe.** So the first 8 sizes share 100 Gbit/s, and sizes 9
  to 16 share another 100 Gbit/s.
- **16 KB of packet memory per pipe**, enough for 8 full-size frames.
- Smallest frame is 46 bytes, the size of the headers plus the error check.

`start.py` stops with an explanation rather than sending less traffic than
asked if any of these is exceeded.

### Checking what was really sent

Each slot counts its own packets. After a run, compare the counters to confirm
the mix came out as configured:

```
bfrt.tf1.pktgen.app_cfg.get(pipe=0, app_id=0)
```

## Changing the packet

At `config.py`:

```python
DESTINATION_MAC = [0x10, 0x41, 0x6d, 0x18, 0x65, 0xfa]
DESTINATION_IP = [192, 168, 1, 11]
```
