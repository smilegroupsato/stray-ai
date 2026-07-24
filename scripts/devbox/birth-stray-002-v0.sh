#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
AGENT_ID="stray-002"
PRIMARY_ID="stray-001"
TEMPLATE_DIR="$REPO_DIR/agents/$AGENT_ID"
AGENTS_DIR="$DATA_DIR/agents"
TARGET_DIR="$AGENTS_DIR/$AGENT_ID"
PRIMARY_DIR="$AGENTS_DIR/$PRIMARY_ID"

if ! git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "Expected an existing repository clone at $REPO_DIR" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime is not executable: $PYTHON_BIN" >&2
  exit 1
fi
if [[ ! -d "$AGENTS_DIR" || -L "$AGENTS_DIR" ]]; then
  echo "Expected a non-symlink persistent agents directory at $AGENTS_DIR" >&2
  exit 1
fi
if [[ ! -d "$PRIMARY_DIR" || -L "$PRIMARY_DIR" ]]; then
  echo "Expected persistent $PRIMARY_ID at $PRIMARY_DIR" >&2
  exit 1
fi
if [[ -e "$TARGET_DIR" || -L "$TARGET_DIR" ]]; then
  echo "Persistent $AGENT_ID already exists; refusing to overwrite: $TARGET_DIR" >&2
  exit 1
fi

TEMPLATE_FILES=(profile.yml memory.md state.json observation-log.md)
for file in "${TEMPLATE_FILES[@]}"; do
  path="$TEMPLATE_DIR/$file"
  if [[ ! -f "$path" || -L "$path" ]]; then
    echo "Required birth template is missing or unsafe: $path" >&2
    exit 1
  fi
done

PRIMARY_FILES=(profile.yml memory.md state.json)
declare -A PRIMARY_HASHES
for file in "${PRIMARY_FILES[@]}"; do
  path="$PRIMARY_DIR/$file"
  if [[ ! -f "$path" || -L "$path" ]]; then
    echo "Required $PRIMARY_ID file is missing or unsafe: $path" >&2
    exit 1
  fi
  PRIMARY_HASHES["$file"]="$(sha256sum "$path" | awk '{print $1}')"
done

"$PYTHON_BIN" - "$TEMPLATE_DIR" "$AGENT_ID" <<'PY'
import json
import sys
from pathlib import Path

import yaml

template = Path(sys.argv[1])
agent_id = sys.argv[2]

profile = yaml.safe_load((template / "profile.yml").read_text(encoding="utf-8"))
state = json.loads((template / "state.json").read_text(encoding="utf-8"))

if not isinstance(profile, dict) or profile.get("id") != agent_id:
    raise SystemExit("profile identity does not match the birth target")
if not isinstance(state, dict):
    raise SystemExit("state template must contain a JSON object")
if state.get("status") != "resting":
    raise SystemExit("birth state must be resting")
if state.get("visit_count") != 0:
    raise SystemExit("birth state must have visit_count 0")
if state.get("document_rummage_count") != 1:
    raise SystemExit("birth state must preserve exactly one repository home-shelf rummage")
if state.get("runtime_rummage_count") != 0 or state.get("llm_rummage_count") != 0:
    raise SystemExit("birth state must not claim a runtime rummage")
PY

STAGING_DIR="$(mktemp -d "$AGENTS_DIR/.${AGENT_ID}.birth.XXXXXX")"
cleanup() {
  if [[ -n "${STAGING_DIR:-}" && -d "$STAGING_DIR" ]]; then
    rm -rf -- "$STAGING_DIR"
  fi
}
trap cleanup EXIT

chmod 0750 "$STAGING_DIR"
for file in "${TEMPLATE_FILES[@]}"; do
  install -m 0640 "$TEMPLATE_DIR/$file" "$STAGING_DIR/$file"
done
mkdir -m 0750 \
  "$STAGING_DIR/rummages" \
  "$STAGING_DIR/visits" \
  "$STAGING_DIR/wake_checks" \
  "$STAGING_DIR/wake_selections" \
  "$STAGING_DIR/visit_requests"

SOURCE_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
STRAY_BIRTH_SOURCE_COMMIT="$SOURCE_COMMIT" \
  "$PYTHON_BIN" - "$STAGING_DIR" "$AGENT_ID" <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

staging = Path(sys.argv[1])
agent_id = sys.argv[2]
files = ("profile.yml", "memory.md", "state.json", "observation-log.md")
manifest = {
    "schema": "stray-persistent-birth-v0",
    "agent_id": agent_id,
    "born_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
    "source_commit": os.environ["STRAY_BIRTH_SOURCE_COMMIT"],
    "template_sha256": {
        name: hashlib.sha256((staging / name).read_bytes()).hexdigest()
        for name in files
    },
    "effects": {
        "wake_invoked": False,
        "visit_invoked": False,
        "scheduler_created": False,
        "report_published": False,
    },
}
(staging / "birth.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
chmod 0640 "$STAGING_DIR/birth.json"

mv "$STAGING_DIR" "$TARGET_DIR"
STAGING_DIR=""

for file in "${PRIMARY_FILES[@]}"; do
  current_hash="$(sha256sum "$PRIMARY_DIR/$file" | awk '{print $1}')"
  if [[ "$current_hash" != "${PRIMARY_HASHES[$file]}" ]]; then
    echo "$PRIMARY_ID changed during birth; manual review is required." >&2
    exit 1
  fi
done

"$PYTHON_BIN" - "$TARGET_DIR" "$PRIMARY_DIR" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
primary = Path(sys.argv[2])
manifest = json.loads((target / "birth.json").read_text(encoding="utf-8"))
state = json.loads((target / "state.json").read_text(encoding="utf-8"))
result = {
    "born": True,
    "agent_id": manifest["agent_id"],
    "persistent_dir": str(target),
    "source_commit": manifest["source_commit"],
    "status": state["status"],
    "visit_count": state["visit_count"],
    "document_rummage_count": state["document_rummage_count"],
    "primary_individual": primary.name,
    "primary_unchanged": True,
    **manifest["effects"],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
