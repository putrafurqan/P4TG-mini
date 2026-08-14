import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config
import flow_plan

# Disables app_enable per (flow, pipe), resending the same field values
# start.py used since mod_with_trigger_timer_periodic replaces the whole
# entry; every profile is disabled since this script doesn't know which one
# was armed.
for profile in config.PROFILES.values():
    plan = flow_plan.build_flow_plan(profile)

    for entry in plan:
        bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
            app_id=entry["app_id"],
            app_enable=False,
            pkt_len=len(entry["packet"]),
            timer_nanosec=entry["timer_nanosec"],
            packets_per_batch_cfg=entry["packets_per_batch_cfg"],
            batch_count_cfg=0,
            pipe=entry["pipe"],
            pipe_local_source_port=entry["local_port"],
            pkt_buffer_offset=entry["pkt_buffer_offset"],
        )
