#!/usr/bin/env python3
"""Presence marker for the Docker entrypoint.

The entrypoint copies the image tree into the run directory only when this
file is missing. The paper geometry runner that used to live here is gone.
The app runs simulation_app_slice.py.
"""

import sys

print(
    "The paper geometry runner has been removed. "
    "Queue a run from the app; it executes simulation_app_slice.py.",
    file=sys.stderr,
)
sys.exit(1)
