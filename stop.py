import os
import sys

this_folder = os.path.dirname(os.path.abspath(__file__))
if this_folder not in sys.path:
    sys.path.append(this_folder)

import config

# Stop by `app_enable` = False
bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(
    app_id=config.GENERATOR_NUMBER,
    app_enable=False,
)
