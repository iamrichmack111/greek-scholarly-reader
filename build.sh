#!/usr/bin/env bash
set -euo pipefail
BASE="${GREEK_LIBRARY_HOME:-$HOME/GREEK-LIBRARY}"
mkdir -p "$BASE/logs" "$BASE/data"
if [[ ! -d "$BASE/classical/perseus/data" ]]; then
 echo "Missing Perseus XML in $BASE/classical/perseus/data" >&2; exit 1
fi
python3 "$(dirname "$0")/build_alignment.py" --base "$BASE" 2>&1 | tee "$BASE/logs/alignment-build.log"
