#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
REPO_URL="${EFP_REPO_URL:-https://github.com/eternal-free-party/free-party-context.git}"
BRANCH="${EFP_BRANCH:-main}"
SOURCE_DIR="${EFP_SOURCE_DIR:-$DATA_DIR/sources/eternal-free-party/free-party-context}"
SNAPSHOT_BASE="${EFP_SNAPSHOT_BASE:-$DATA_DIR/venues/eternal-free-party}"
MAX_FILES="${EFP_MAX_FILES:-500}"
MAX_FILE_BYTES="${EFP_MAX_FILE_BYTES:-524288}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$(dirname "$SOURCE_DIR")" "$SNAPSHOT_BASE"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone \
    --depth 1 \
    --filter=blob:none \
    --no-tags \
    --branch "$BRANCH" \
    "$REPO_URL" \
    "$SOURCE_DIR" >&2
else
  actual_url="$(git -C "$SOURCE_DIR" remote get-url origin)"
  if [[ "$actual_url" != "$REPO_URL" ]]; then
    echo "Refusing to update unexpected source remote: $actual_url" >&2
    exit 1
  fi
  if [[ -n "$(git -C "$SOURCE_DIR" status --porcelain)" ]]; then
    echo "Refusing to update a dirty source checkout: $SOURCE_DIR" >&2
    exit 1
  fi
  git -C "$SOURCE_DIR" fetch --depth 1 --no-tags origin "$BRANCH" >&2
  git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD >/dev/null
fi

COMMIT="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
SNAPSHOT_DIR="$SNAPSHOT_BASE/$COMMIT"

if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  TMP_DIR="$SNAPSHOT_BASE/.tmp-$COMMIT-$$"
  rm -rf "$TMP_DIR"
  mkdir -p "$TMP_DIR"
  trap 'rm -rf "$TMP_DIR"' EXIT

  FILE_COUNT="$($PYTHON_BIN - "$SOURCE_DIR" "$TMP_DIR" "$MAX_FILES" "$MAX_FILE_BYTES" <<'PY'
from __future__ import annotations

import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
max_files = int(sys.argv[3])
max_bytes = int(sys.argv[4])
allowed = {".md", ".markdown", ".txt"}
skipped_parts = {".git", "node_modules", ".venv", "dist", "build"}

files: list[Path] = []
for path in sorted(source.rglob("*")):
    if path.is_symlink() or not path.is_file():
        continue
    relative = path.relative_to(source)
    if any(part in skipped_parts for part in relative.parts):
        continue
    if path.suffix.lower() not in allowed:
        continue
    if path.stat().st_size > max_bytes:
        continue
    files.append(path)

if len(files) > max_files:
    raise SystemExit(f"snapshot exceeds file limit: {len(files)} > {max_files}")

for path in files:
    relative = path.relative_to(source)
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)

print(len(files))
PY
)"

  for required in README.md REPOSITORY_CONTEXT.md AGENTS.md; do
    if [[ ! -f "$TMP_DIR/$required" ]]; then
      echo "Required venue file missing from snapshot: $required" >&2
      exit 1
    fi
  done

  CAPTURED_AT="$($PYTHON_BIN - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"))
PY
)"

  cat > "$TMP_DIR/SNAPSHOT.txt" <<EOF
source_repository=$REPO_URL
source_branch=$BRANCH
source_commit=$COMMIT
captured_at=$CAPTURED_AT
copied_text_files=$FILE_COUNT
max_file_bytes=$MAX_FILE_BYTES
EOF

  chmod -R a-w "$TMP_DIR"
  mv "$TMP_DIR" "$SNAPSHOT_DIR"
  trap - EXIT
fi

ln -sfn "$COMMIT" "$SNAPSHOT_BASE/.current-new"
mv -Tf "$SNAPSHOT_BASE/.current-new" "$SNAPSHOT_BASE/current"

printf '%s\n' "$SNAPSHOT_DIR"
