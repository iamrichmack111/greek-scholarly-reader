#!/usr/bin/env bash
set -euo pipefail
BASE="${GREEK_LIBRARY_HOME:-$HOME/GREEK-LIBRARY}"
DEST="${1:-$BASE/releases/local-snapshots}"
mkdir -p "$DEST"
command -v sqlite3 >/dev/null || { echo 'Install sqlite3 CLI first'; exit 1; }
command -v zstd >/dev/null || { echo 'Install zstd first'; exit 1; }
for f in scholarly.db alignments_v6.db; do
 if [[ -f "$BASE/data/$f" ]]; then
  sqlite3 "$BASE/data/$f" ".backup '$DEST/$f'"
  test "$(sqlite3 "$DEST/$f" 'PRAGMA integrity_check;')" = ok || exit 1
  zstd -f -T2 -3 --rm "$DEST/$f"
 fi
done
(cd "$DEST" && sha256sum ./*.zst > SHA256SUMS && sha256sum -c SHA256SUMS)
echo 'LOCAL SNAPSHOTS ONLY. Do not publish until the edition-level rights audit is complete.'
