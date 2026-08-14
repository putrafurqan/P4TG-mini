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

Prompts for which profile to run (Enter picks `config.ACTIVE_PROFILE`), then
prints each flow's achieved pps/Gbit/s and pipe assignment.

**3. Stop the traffic.**

```bash
$SDE/run_bfshell.sh -b ~/exp/P4TG-mini/stop.py
```

Disables every flow in every profile, regardless of which one was started.

## Profiles and flows

All packet templates live in `config.PROFILES`. A profile is a list of
flows; a flow is one packet template plus its own rate and (optionally) its
own pipes.

```python
PROFILES = {
    "profile_name": {
        "flows": [
            {
                "name": "flow_name",
                "app_id": 0,
                "pipes": [0, 1, 2, 3],       # optional - omit to auto-assign
                "frame_size": 1518,           # bytes on the wire, includes 4-byte FCS
                "ethernet": {"source_mac": [...], "destination_mac": [...]},
                "ip": {"source_ip": [...], "destination_ip": [...]},
                "udp": {"source_port": ..., "destination_port": ...},
                "rate": {"timer_nanosec": 6152, "packets_per_batch": 5},  # or {"target_pps": N}
            },
        ],
    },
}
```

## Setting a flow's rate

| Form | Meaning |
|---|---|
| `{"timer_nanosec": T, "packets_per_batch": P}` | P packets fired every T ns, per pipe. Requires `"pipes"` set explicitly. |
| `{"target_pps": N}` | N packets/sec total, split evenly across whichever pipes the flow ends up on. |

```
speed in Gbit/s (per pipe) = packets_per_batch * (frame_size + 20) * 8 / timer_nanosec
```

Examples (1518-byte frame, single pipe):

| Timer | Packets per batch | Speed |
|---|---|---|
| 12304 | 1 | 1 Gbit/s |
| 6152 | 5 | 10 Gbit/s |
| 6152 | 25 | 50 Gbit/s |
| 3076 | 25 | 100 Gbit/s |

## Setting a flow's pipes

Omit `"pipes"` and `flow_plan.pack_pipes()` assigns the flow the minimum
number of unclaimed pipes needed to keep each pipe under
`flow_plan.PIPE_CAPACITY_GBIT` (100 Gbit/s), splitting the flow's rate
evenly across them. Set `"pipes"` explicitly (e.g. `[0, 1, 2, 3]`) to pin a
flow to specific pipes yourself — required for the raw CBR rate form.

Every port in `config.PORTS` receives every active flow's traffic
(multicast fan-out duplicates, it doesn't split), so per-port load is the
sum of all flows in the running profile, not divided by port count.

## Changing a flow's packet

Edit the flow's `ethernet`/`ip`/`udp`/`frame_size` fields directly.
`destination_mac`/`destination_ip` are placeholders — the switch rewrites
them per output port from `config.PORTS`.
