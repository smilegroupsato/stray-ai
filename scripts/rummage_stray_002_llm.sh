#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"

if [[ -z "${STRAY_LLM_MODEL:-}" ]]; then
  echo "STRAY_LLM_MODEL is required." >&2
  exit 1
fi
if [[ ! -d "$DATA_DIR/agents/stray-002" || -L "$DATA_DIR/agents/stray-002" ]]; then
  echo "Persistent stray-002 was not found safely." >&2
  exit 1
fi

export STRAY_LLM_BASE_URL="${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="${STRAY_LLM_HTTP_TIMEOUT:-150}"
export STRAY_LLM_MAX_TOKENS="${STRAY_LLM_MAX_TOKENS:-1400}"
export STRAY_RUMMAGE_BRAIN_TIMEOUT="${STRAY_RUMMAGE_BRAIN_TIMEOUT:-180}"

BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_rummage_brain.py"
ROUTE=(
  README.md
  docs/roadmap.md
  docs/architecture.md
  docs/memory-provenance.md
  docs/current-board.md
  registry/current_board.yml
  handoffs/codex/2026.07.23_04_multi_venue_wake_selection_v0.md
)

exec "$REPO_DIR/.venv/bin/stray-ai-rummage" \
  --agent "$DATA_DIR/agents/stray-002" \
  --repository-root "$REPO_DIR" \
  --route "${ROUTE[@]}" \
  --confirm-agent-id stray-002 \
  --brain-command "$BRAIN_COMMAND" \
  --brain-label "$STRAY_LLM_MODEL" \
  --brain-timeout "$STRAY_RUMMAGE_BRAIN_TIMEOUT" \
  "$@"
