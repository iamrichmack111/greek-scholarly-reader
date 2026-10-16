#!/usr/bin/env bash
set -euo pipefail
BASE="${GREEK_LIBRARY_HOME:-$HOME/GREEK-LIBRARY}"
exec python3 "$(dirname "$0")/server.py" --base "$BASE" --host "${HOST:-127.0.0.1}" --port "${PORT:-8799}"
