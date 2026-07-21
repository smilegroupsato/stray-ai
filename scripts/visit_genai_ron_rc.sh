#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
SNAPSHOT_ROOT="${GENAI_RON_SNAPSHOT_BASE:-$DATA_DIR/venues/genai-ron-rc}"
SNAPSHOT_DIR="${STRAY_GENAI_RON_SNAPSHOT_DIR:-}"
EXPECTED_REPOSITORY="${GENAI_RON_REPO_URL:-https://github.com/smilegroupsato/web-genai-ron-jp.git}"

if [[ -z "$SNAPSHOT_DIR" ]]; then
  if [[ ! -L "$SNAPSHOT_ROOT/current" ]]; then
    echo "No current GENAI-RON snapshot was found." >&2
    echo "Create and inspect one separately with scripts/snapshot_genai_ron_rc.sh." >&2
    exit 1
  fi
  SNAPSHOT_DIR="$(readlink -f "$SNAPSHOT_ROOT/current")"
fi

if [[ ! -d "$SNAPSHOT_DIR" || -L "$SNAPSHOT_DIR" ]]; then
  echo "Invalid GENAI-RON snapshot directory: $SNAPSHOT_DIR" >&2
  exit 1
fi

for required in README.md CHAT_HISTORY.md AFTERHOURS.md SNAPSHOT.txt; do
  if [[ ! -f "$SNAPSHOT_DIR/$required" || -L "$SNAPSHOT_DIR/$required" ]]; then
    echo "Required GENAI-RON snapshot file missing or unsafe: $required" >&2
    exit 1
  fi
done

mapfile -t entries < <(find "$SNAPSHOT_DIR" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort)
expected=(AFTERHOURS.md CHAT_HISTORY.md README.md SNAPSHOT.txt)
if [[ "${entries[*]}" != "${expected[*]}" ]]; then
  echo "GENAI-RON snapshot contains entries outside the approved manifest." >&2
  printf 'Observed: %s\n' "${entries[*]}" >&2
  exit 1
fi

SNAPSHOT_ID="$(basename "$SNAPSHOT_DIR")"
grep -Fqx "venue_id=genai-ron-rc" "$SNAPSHOT_DIR/SNAPSHOT.txt" || {
  echo "GENAI-RON snapshot venue identity mismatch." >&2
  exit 1
}
grep -Fqx "source_repository=$EXPECTED_REPOSITORY" "$SNAPSHOT_DIR/SNAPSHOT.txt" || {
  echo "GENAI-RON snapshot repository mismatch." >&2
  exit 1
}
grep -Fqx "source_commit=$SNAPSHOT_ID" "$SNAPSHOT_DIR/SNAPSHOT.txt" || {
  echo "GENAI-RON snapshot commit mismatch." >&2
  exit 1
}

if [[ ! -x "$DATA_DIR/run-first-visitor.sh" ]]; then
  echo "Devbox habitat launcher not found: $DATA_DIR/run-first-visitor.sh" >&2
  echo "Run scripts/setup_devbox.sh first." >&2
  exit 1
fi

export STRAY_LOCAL_ROOT="$SNAPSHOT_DIR"
export STRAY_ENTRANCE="$SNAPSHOT_DIR/README.md"
exec "$DATA_DIR/run-first-visitor.sh" \
  --arrival-path CHAT_HISTORY.md AFTERHOURS.md \
  "$@"
