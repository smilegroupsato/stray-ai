#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
OLLAMA_BIN="${OLLAMA_BIN:-ollama}"
MODEL_NAME="${STRAY_RUMMAGE_MODEL:-stray-qwen3.5-9b-16k}"
MODELFILE="$REPO_DIR/models/stray-qwen3.5-9b-16k.Modelfile"
BASE_MODEL="qwen3.5:9b"
EXPECTED_CONTEXT="16384"

if [[ ! -x "$(command -v "$OLLAMA_BIN" 2>/dev/null)" ]]; then
  echo "Ollama executable was not found: $OLLAMA_BIN" >&2
  exit 1
fi
if [[ ! -f "$MODELFILE" || -L "$MODELFILE" ]]; then
  echo "Trusted rummage Modelfile is missing or unsafe: $MODELFILE" >&2
  exit 1
fi
if ! "$OLLAMA_BIN" show "$BASE_MODEL" >/dev/null 2>&1; then
  echo "Required local base model is unavailable: $BASE_MODEL" >&2
  echo "No model was pulled automatically." >&2
  exit 1
fi

"$OLLAMA_BIN" create "$MODEL_NAME" -f "$MODELFILE"

MODEL_CONFIG="$("$OLLAMA_BIN" show "$MODEL_NAME" --modelfile)"
if ! grep -Eq '^[[:space:]]*PARAMETER[[:space:]]+num_ctx[[:space:]]+16384[[:space:]]*$' \
  <<<"$MODEL_CONFIG"; then
  echo "Created model did not report num_ctx $EXPECTED_CONTEXT: $MODEL_NAME" >&2
  exit 1
fi

echo "Stray-002 rummage model prepared."
echo "Model: $MODEL_NAME"
echo "Context: $EXPECTED_CONTEXT"
