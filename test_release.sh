#!/usr/bin/env bash
set -euo pipefail

BASE="$HOME/GREEK-LIBRARY"
RELEASE="$BASE/releases"
TEST="$RELEASE/v6.3.0-integration-test"
PORT=8801

mkdir -p "$TEST/data"

echo "=== CONFIGURING TEST DATABASES ==="

ln -sfn \
  "$RELEASE/v6.3.0-dictionary-candidate/scholarly-with-lexicon.db" \
  "$TEST/data/scholarly.db"

ln -sfn \
  "$RELEASE/v6.3.0-candidate/alignments-candidate.db" \
  "$TEST/data/alignments_v6.db"

echo
echo "=== STARTING READER ==="

python3 server.py \
  --base "$TEST" \
  --host 127.0.0.1 \
  --port "$PORT" \
  > "$TEST/server.log" 2>&1 &

PID=$!

trap 'kill "$PID" 2>/dev/null || true' EXIT

echo
echo "=== RUNNING INTEGRATION TESTS ==="

python3 - "$PORT" <<'PY'
import json
import sys
import time
import urllib.request
import urllib.parse

port = sys.argv[1]
base = f"http://127.0.0.1:{port}"

def get(path):
    with urllib.request.urlopen(
        base + path,
        timeout=15
    ) as response:
        return response.status, response.read().decode("utf-8")

# Wait for server startup.
for attempt in range(30):
    try:
        status, html = get("/")
        break
    except Exception:
        time.sleep(0.5)
else:
    raise RuntimeError("Server failed to start")

print("[1/4] Homepage")
assert status == 200
assert "Greek Parallel Reader" in html
print("PASS")

print("[2/4] Dictionary lookup")
word = urllib.parse.quote("λόγος")
status, body = get("/api/word?word=" + word)

data = json.loads(body)
assert status == 200
assert isinstance(data.get("entries"), list)
assert len(data["entries"]) > 0, data
print("PASS —", len(data["entries"]), "entries")

print("[3/4] Alignment search")
query = urllib.parse.quote("the")
status, body = get("/api/search?q=" + query)

data = json.loads(body)
assert status == 200
assert isinstance(data, list)
print("PASS —", len(data), "results")

print("[4/4] Search page")
status, html = get("/?q=the")
assert status == 200
assert "Greek Parallel Reader" in html
print("PASS")

print()
print("ALL HTTP INTEGRATION TESTS PASSED")
PY

echo
echo "=== SERVER LOG ==="
tail -n 12 "$TEST/server.log"
