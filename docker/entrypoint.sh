#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${RIMAG_WORKDIR:-/work}"

mkdir -p "$WORKDIR"

# Copy the source tree from the image into the writable run directory
# only if the run directory does not already contain the app runner.
if [ ! -f "$WORKDIR/simulation_app_slice.py" ]; then
    cp -a /opt/rimag/. "$WORKDIR/"
fi

cd "$WORKDIR"

# simlib reads simsettings.json from the current working directory.
# Let RIMAG_THREADS override it reproducibly.
if [ -n "${RIMAG_THREADS:-}" ]; then
    printf '{ "threads": %s }\n' "$RIMAG_THREADS" > simsettings.json
elif [ ! -f simsettings.json ]; then
    printf '{ "threads": 20 }\n' > simsettings.json
fi

exec "$@"
