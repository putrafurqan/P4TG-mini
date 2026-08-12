import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config

# Every slot on both pipes is disabled, not only the ones in the current
# STREAMS. A run started with a different configuration leaves slots armed that
# are no longer listed, and those have to stop as well.

stopped = 0

for pipe in range(len(config.GENERATOR_PORTS)):
    for app_id in range(8):
        try:
            bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
                app_id=app_id,
                pipe=pipe,
                app_enable=False,
            )
            stopped = stopped + 1
        except:
            # A slot that was never configured cannot be disabled, which is
            # fine: it is not running.
            pass

print(f"Stopped {stopped} generator slots.")
