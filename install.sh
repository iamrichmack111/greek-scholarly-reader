#!/usr/bin/env bash
set -euo pipefail
BASE="${GREEK_LIBRARY_HOME:-$HOME/GREEK-LIBRARY}"
mkdir -p "$BASE/data" "$BASE/logs"
command -v python3 >/dev/null || { echo 'Python 3 required'; exit 1; }
python3 - <<'PY2'
import sqlite3
c=sqlite3.connect(':memory:')
c.execute('CREATE VIRTUAL TABLE t USING fts5(x)')
print('Python and SQLite FTS5: OK')
PY2
printf '\nLibrary location: %s\n' "$BASE"
for name in scholarly.db alignments_v6.db; do
 if [[ -f "$BASE/data/$name" ]]; then
  echo "FOUND $name"
 else
  echo "MISSING $name"
 fi
done
if [[ -f "$BASE/data/alignments_v6.db" ]]; then
 echo 'Start reader: ./run.sh'
else
 echo 'Build alignments after obtaining Perseus sources: ./build.sh'
fi
echo 'Public database downloads are deliberately disabled pending edition-by-edition licensing review.'
