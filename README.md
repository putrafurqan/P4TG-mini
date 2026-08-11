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

## Throughput Configuration

At `config.py`:

```python
TIMER_NANOSECONDS = 6152
PACKETS_PER_TIMER = 5
```

```
speed in Gbit/s  =  PACKETS_PER_TIMER * (FRAME_SIZE + 20) * 8  /  TIMER_NANOSECONDS
```

Examples (1518 Bytes):

| Timer | Packets per timer | Speed |
|---|---|---|
| 12304 | 1 | 1 Gbit/s |
| 6152 | 5 | 10 Gbit/s |
| 6152 | 25 | 50 Gbit/s |
| 3076 | 25 | 100 Gbit/s |

## Changing the packet

At `config.py`:

```python
DESTINATION_MAC = [0x10, 0x41, 0x6d, 0x18, 0x65, 0xfa]
DESTINATION_IP = [192, 168, 1, 11]
```
