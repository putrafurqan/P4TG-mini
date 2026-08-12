import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

# See the note in start.py: bfshell reuses one Python process across runs,
# so drop any cached copy of config before reading it.
if "config" in sys.modules:
    del sys.modules["config"]

import config

# Every slot on every pipe is switched off, not only the ones the current
# config.py asks for. That way a slot left running by an earlier, larger
# configuration is cleared too.

stopped = 0

for pipe in range(len(config.GENERATOR_PORTS)):
    for slot in range(config.MAX_SLOTS_PER_PIPE):
        try:
            bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
                pipe=pipe,
                app_id=slot,
                app_enable=False,
            )
            stopped = stopped + 1
        except:
            pass

print(f"Stopped {stopped} generator slots.")
