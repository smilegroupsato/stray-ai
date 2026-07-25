#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
SNAPSHOT_DIR="${1:-}"
SNAPSHOT_BASE="$DATA_DIR/venues/eternal-free-party"
RUNNER="$DATA_DIR/run-first-visitor.sh"

if [[ -z "$SNAPSHOT_DIR" ]]; then
  echo "Usage: bash $0 SNAPSHOT_DIR" >&2
  exit 2
fi
if [[ ! -d "$SNAPSHOT_BASE" || -L "$SNAPSHOT_BASE" ]]; then
  echo "EFP snapshot base is missing or unsafe: $SNAPSHOT_BASE" >&2
  exit 1
fi
if [[ ! -d "$SNAPSHOT_DIR" || -L "$SNAPSHOT_DIR" ]]; then
  echo "EFP snapshot is missing or unsafe: $SNAPSHOT_DIR" >&2
  exit 1
fi
if [[ ! -f "$RUNNER" || -L "$RUNNER" ]]; then
  echo "Persistent Visit runner is missing or unsafe: $RUNNER" >&2
  exit 1
fi

SNAPSHOT_REAL="$(realpath -e "$SNAPSHOT_DIR")"
SNAPSHOT_BASE_REAL="$(realpath -e "$SNAPSHOT_BASE")"
if [[ "$(dirname "$SNAPSHOT_REAL")" != "$SNAPSHOT_BASE_REAL" ]]; then
  echo "EFP snapshot is outside the trusted base." >&2
  exit 1
fi
SNAPSHOT_ID="$(basename "$SNAPSHOT_REAL")"
if ! [[ "$SNAPSHOT_ID" =~ ^[0-9a-f]{40}$ ]]; then
  echo "EFP snapshot identity is not a commit SHA." >&2
  exit 1
fi
for required in README.md REPOSITORY_CONTEXT.md AGENTS.md; do
  if [[ ! -f "$SNAPSHOT_REAL/$required" || -L "$SNAPSHOT_REAL/$required" ]]; then
    echo "Required EFP reception file is missing or unsafe: $required" >&2
    exit 1
  fi
done

export STRAY_LLM_MODEL="${STRAY_LLM_MODEL:-stray-qwen3.5-9b-16k}"
export STRAY_LLM_BASE_URL="${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="${STRAY_LLM_HTTP_TIMEOUT:-150}"
export STRAY_LLM_MAX_TOKENS="${STRAY_LLM_MAX_TOKENS:-600}"
export STRAY_BRAIN_TIMEOUT="${STRAY_BRAIN_TIMEOUT:-180}"
export STRAY_LOCAL_ROOT="$SNAPSHOT_REAL"
export STRAY_ENTRANCE="$SNAPSHOT_REAL/README.md"

BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_brain.py"
exec bash "$RUNNER" \
  --arrival-path REPOSITORY_CONTEXT.md AGENTS.md \
  --brain command \
  --brain-command "$BRAIN_COMMAND" \
  --brain-label "$STRAY_LLM_MODEL" \
  --brain-timeout "$STRAY_BRAIN_TIMEOUT"
