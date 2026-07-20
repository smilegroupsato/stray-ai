#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "Expected an existing clone at $REPO_DIR" >&2
  echo "Clone first: git clone https://github.com/smilegroupsato/stray-ai.git $REPO_DIR" >&2
  exit 1
fi

mkdir -p \
  "$DATA_DIR/agents/stray-001" \
  "$DATA_DIR/agents/stray-001/wake_checks" \
  "$DATA_DIR/sources" \
  "$DATA_DIR/venues" \
  "$DATA_DIR/outbox/traces" \
  "$DATA_DIR/reports" \
  "$DATA_DIR/backups"

if [[ ! -d "$REPO_DIR/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$REPO_DIR/.venv"
fi

"$REPO_DIR/.venv/bin/python" -m pip install --upgrade pip
"$REPO_DIR/.venv/bin/python" -m pip install -e "$REPO_DIR[dev]"

for file in profile.yml memory.md state.json; do
  if [[ ! -e "$DATA_DIR/agents/stray-001/$file" ]]; then
    cp "$REPO_DIR/agents/stray-001/$file" "$DATA_DIR/agents/stray-001/$file"
  fi
done

"$REPO_DIR/.venv/bin/stray-ai-migrate" "$DATA_DIR/agents/stray-001"

cat > "$DATA_DIR/run-first-visitor.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
LOCAL_ROOT="\${STRAY_LOCAL_ROOT:-$DATA_DIR/venues}"
ENTRANCE="\${STRAY_ENTRANCE:-\$LOCAL_ROOT/README.md}"
if [[ ! -d "\$LOCAL_ROOT" ]]; then
  echo "Venue root not found: \$LOCAL_ROOT" >&2
  exit 1
fi
if [[ ! -f "\$ENTRANCE" ]]; then
  echo "Entrance not found: \$ENTRANCE" >&2
  echo "Place a bounded venue under \$LOCAL_ROOT or set STRAY_ENTRANCE." >&2
  exit 1
fi
COMMAND=(
  "$REPO_DIR/.venv/bin/stray-ai"
  --agent "$DATA_DIR/agents/stray-001"
  --local-root "\$LOCAL_ROOT"
  --entrance "\$ENTRANCE"
  --outbox "$DATA_DIR/outbox/traces"
)
RESULT="\$("\${COMMAND[@]}" "\$@")"
printf '%s\n' "\$RESULT"
if ! "$REPO_DIR/.venv/bin/stray-ai-report" \
  --agents-dir "$DATA_DIR/agents" \
  --primary-agent stray-001 \
  --output-dir "$DATA_DIR/reports"; then
  echo "Visit completed, but HTML report collection generation failed." >&2
fi
EOF
chmod 750 "$DATA_DIR/run-first-visitor.sh"

cat > "$DATA_DIR/generate-latest-report.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$REPO_DIR/.venv/bin/stray-ai-report" \
  --agents-dir "$DATA_DIR/agents" \
  --primary-agent stray-001 \
  --output-dir "$DATA_DIR/reports"
EOF
chmod 750 "$DATA_DIR/generate-latest-report.sh"

cat > "$DATA_DIR/snapshot-eternal-free-party.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec bash "$REPO_DIR/scripts/snapshot_eternal_free_party.sh" "\$@"
EOF
chmod 750 "$DATA_DIR/snapshot-eternal-free-party.sh"

cat > "$DATA_DIR/visit-eternal-free-party.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SNAPSHOT_DIR="\$(bash "$REPO_DIR/scripts/snapshot_eternal_free_party.sh")"
echo "Eternal Free Party snapshot: \$SNAPSHOT_DIR" >&2
for required in README.md REPOSITORY_CONTEXT.md AGENTS.md; do
  if [[ ! -f "\$SNAPSHOT_DIR/\$required" ]]; then
    echo "Required reception file missing: \$SNAPSHOT_DIR/\$required" >&2
    exit 1
  fi
done
export STRAY_LOCAL_ROOT="\$SNAPSHOT_DIR"
export STRAY_ENTRANCE="\$SNAPSHOT_DIR/README.md"
exec "$DATA_DIR/run-first-visitor.sh" \
  --arrival-path REPOSITORY_CONTEXT.md AGENTS.md \
  "\$@"
EOF
chmod 750 "$DATA_DIR/visit-eternal-free-party.sh"

cat > "$DATA_DIR/visit-eternal-free-party-llm.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -z "\${STRAY_LLM_MODEL:-}" ]]; then
  echo "STRAY_LLM_MODEL is required." >&2
  exit 1
fi
export STRAY_LLM_BASE_URL="\${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="\${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="\${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="\${STRAY_LLM_HTTP_TIMEOUT:-150}"
export STRAY_LLM_MAX_TOKENS="\${STRAY_LLM_MAX_TOKENS:-400}"
export STRAY_BRAIN_TIMEOUT="\${STRAY_BRAIN_TIMEOUT:-180}"
BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_brain.py"
exec "$DATA_DIR/visit-eternal-free-party.sh" \
  --brain command \
  --brain-command "\$BRAIN_COMMAND" \
  --brain-label "\$STRAY_LLM_MODEL" \
  --brain-timeout "\$STRAY_BRAIN_TIMEOUT" \
  "\$@"
EOF
chmod 750 "$DATA_DIR/visit-eternal-free-party-llm.sh"

cat > "$DATA_DIR/check-wake-eternal-free-party.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SNAPSHOT_ROOT="$DATA_DIR/venues/eternal-free-party"
SNAPSHOT_DIR="\${STRAY_WAKE_SNAPSHOT_DIR:-}"
if [[ -z "\$SNAPSHOT_DIR" ]]; then
  SNAPSHOT_DIR="\$(find "\$SNAPSHOT_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null \
    | sort -n \
    | tail -1 \
    | cut -d' ' -f2-)"
fi
if [[ -z "\$SNAPSHOT_DIR" || ! -d "\$SNAPSHOT_DIR" ]]; then
  echo "No existing Eternal Free Party snapshot was found." >&2
  echo "This wake check does not fetch a venue. Create a snapshot separately first." >&2
  exit 1
fi
SNAPSHOT_ID="\$(basename "\$SNAPSHOT_DIR")"
exec "$REPO_DIR/.venv/bin/stray-ai-wake" \
  --agent "$DATA_DIR/agents/stray-001" \
  --candidate-snapshot-id "\$SNAPSHOT_ID" \
  "\$@"
EOF
chmod 750 "$DATA_DIR/check-wake-eternal-free-party.sh"

cat > "$DATA_DIR/check-wake-eternal-free-party-llm.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -z "\${STRAY_LLM_MODEL:-}" ]]; then
  echo "STRAY_LLM_MODEL is required." >&2
  exit 1
fi
export STRAY_LLM_BASE_URL="\${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="\${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="\${STRAY_LLM_REASONING_EFFORT:-none}"
export STRAY_LLM_HTTP_TIMEOUT="\${STRAY_LLM_HTTP_TIMEOUT:-120}"
export STRAY_LLM_MAX_TOKENS="\${STRAY_LLM_MAX_TOKENS:-300}"
export STRAY_WAKE_BRAIN_TIMEOUT="\${STRAY_WAKE_BRAIN_TIMEOUT:-150}"
BRAIN_COMMAND="$REPO_DIR/.venv/bin/python $REPO_DIR/scripts/openai_compatible_wake_brain.py"
exec "$DATA_DIR/check-wake-eternal-free-party.sh" \
  --brain command \
  --brain-command "\$BRAIN_COMMAND" \
  --brain-label "\$STRAY_LLM_MODEL" \
  --brain-timeout "\$STRAY_WAKE_BRAIN_TIMEOUT" \
  "\$@"
EOF
chmod 750 "$DATA_DIR/check-wake-eternal-free-party-llm.sh"

"$REPO_DIR/.venv/bin/python" -m pytest "$REPO_DIR/tests"

echo "Devbox habitat prepared."
echo "Repository: $REPO_DIR"
echo "Persistent data: $DATA_DIR"
echo "Collection index: $DATA_DIR/reports/index.html"
echo "Primary visits: $DATA_DIR/reports/visits.html"
echo "Primary latest report: $DATA_DIR/reports/latest.html"
echo "Primary observed map: $DATA_DIR/reports/map.html"
echo "Mock EFP visit: $DATA_DIR/visit-eternal-free-party.sh"
echo "LLM EFP visit: $DATA_DIR/visit-eternal-free-party-llm.sh"
echo "Deterministic EFP wake check: $DATA_DIR/check-wake-eternal-free-party.sh"
echo "LLM EFP wake check: $DATA_DIR/check-wake-eternal-free-party-llm.sh"
