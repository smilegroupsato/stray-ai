#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
SGOS_REPO_KEY="${STRAY_002_SGOS_REPO_KEY:-sgos-pkm-core}"

if [[ ! -d "$DATA_DIR/agents/stray-002" || -L "$DATA_DIR/agents/stray-002" ]]; then
  echo "Persistent stray-002 was not found safely." >&2
  exit 1
fi

case "$SGOS_REPO_KEY" in
  sgos-pkm-core)
    TARGET_REPO_DIR="${STRAY_002_SGOS_PKM_CORE_REPO_DIR:-/srv/sgos/repos/sgos-pkm-core}"
    TARGET_LABEL="sgos-pkm-core"
    CANDIDATES=(
      context_packs/SGOS_COMPACT_CONTEXT.md
      context_packs/SGOS_PKM_CONTEXT.md
      context_packs/ACTIVE_PROJECTS_CONTEXT.md
      README.md
      NEXT.md
      ATTENTION.md
      HISTORY.md
      docs/CHARTER.md
      docs/charter.md
      docs/steward-charter.md
      docs/architecture.md
      docs/services.md
    )
    ;;
  sgos-console)
    TARGET_REPO_DIR="${STRAY_002_SGOS_CONSOLE_REPO_DIR:-/srv/sgos/repos/sgos-console}"
    TARGET_LABEL="sgos-console"
    CANDIDATES=(
      README.md
      NEXT.md
      ATTENTION.md
      HISTORY.md
      docs/2026.08.20_01_console_chat_handoff.md
      docs/CHARTER.md
      docs/charter.md
      docs/steward-charter.md
      docs/architecture.md
      docs/services.md
    )
    ;;
  *)
    echo "Unsupported SGOS rummage target: $SGOS_REPO_KEY" >&2
    echo "Supported targets: sgos-pkm-core, sgos-console" >&2
    exit 1
    ;;
esac

if [[ ! -d "$TARGET_REPO_DIR" || -L "$TARGET_REPO_DIR" ]]; then
  echo "SGOS repository was not found safely: $TARGET_REPO_DIR" >&2
  exit 1
fi
if ! git -C "$TARGET_REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "SGOS rummage target is not a git repository: $TARGET_REPO_DIR" >&2
  exit 1
fi

export STRAY_LLM_MODEL="${STRAY_LLM_MODEL:-stray-qwen3.5-9b-16k}"
export STRAY_LLM_BASE_URL="${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="${STRAY_LLM_HTTP_TIMEOUT:-150}"
export STRAY_LLM_MAX_TOKENS="${STRAY_LLM_MAX_TOKENS:-4096}"
export STRAY_RUMMAGE_BRAIN_TIMEOUT="${STRAY_RUMMAGE_BRAIN_TIMEOUT:-180}"

BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_console_desk_rummage_brain.py"

ROUTE=()
for candidate in "${CANDIDATES[@]}"; do
  if [[ -f "$TARGET_REPO_DIR/$candidate" && ! -L "$TARGET_REPO_DIR/$candidate" ]]; then
    ROUTE+=("$candidate")
  fi
  if (( ${#ROUTE[@]} >= 7 )); then
    break
  fi
done

if (( ${#ROUTE[@]} < 3 )); then
  echo "Need at least three safe SGOS documents in $TARGET_LABEL; found ${#ROUTE[@]}." >&2
  printf 'Found route: %s\n' "${ROUTE[*]:-none}" >&2
  exit 1
fi

exec "$REPO_DIR/.venv/bin/stray-ai-rummage" \
  --agent "$DATA_DIR/agents/stray-002" \
  --repository-root "$TARGET_REPO_DIR" \
  --route "${ROUTE[@]}" \
  --confirm-agent-id stray-002 \
  --brain-command "$BRAIN_COMMAND" \
  --brain-label "$STRAY_LLM_MODEL/$TARGET_LABEL-sgos-shelf" \
  --brain-timeout "$STRAY_RUMMAGE_BRAIN_TIMEOUT" \
  "$@"
