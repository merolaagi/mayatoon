#!/bin/bash
# Run MayaToon in the foreground (stop the service first: ./ctl.sh stop)
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
exec python3 server.py --host "${MAYATOON_HOST:-127.0.0.1}" --port "${MAYATOON_PORT:-47219}"
