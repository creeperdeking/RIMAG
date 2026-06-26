#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${RIMAG_WORKDIR:-/work}"

mkdir -p "$WORKDIR"

# Copy the source tree from the image into the writable run directory
# only if the run directory does not already contain a checkout/copy.
if [ ! -f "$WORKDIR/start_sim.py" ]; then
    cp -a /opt/rimag/. "$WORKDIR/"
fi

cd "$WORKDIR"

# start_sim/simlib currently read simsettings.json from the current
# working directory. Let RIMAG_THREADS override it reproducibly.
if [ -n "${RIMAG_THREADS:-}" ]; then
    printf '{ "threads": %s }\n' "$RIMAG_THREADS" > simsettings.json
elif [ ! -f simsettings.json ]; then
    printf '{ "threads": 20 }\n' > simsettings.json
fi

exec "$@"
