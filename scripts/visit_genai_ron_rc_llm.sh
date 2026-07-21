#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"

if [[ -z "${STRAY_LLM_MODEL:-}" ]]; then
  echo "STRAY_LLM_MODEL is required." >&2
  exit 1
fi

export STRAY_LLM_BASE_URL="${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="${STRAY_LLM_HTTP_TIMEOUT:-150}"
export STRAY_LLM_MAX_TOKENS="${STRAY_LLM_MAX_TOKENS:-400}"
export STRAY_BRAIN_TIMEOUT="${STRAY_BRAIN_TIMEOUT:-180}"
BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_brain.py"

exec bash "$REPO_DIR/scripts/visit_genai_ron_rc.sh" \
  --brain command \
  --brain-command "$BRAIN_COMMAND" \
  --brain-label "$STRAY_LLM_MODEL" \
  --brain-timeout "$STRAY_BRAIN_TIMEOUT" \
  "$@"
