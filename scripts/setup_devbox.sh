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
VISIT_FILE="\$("$REPO_DIR/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["visit_file"])' <<<"\$RESULT")"
if ! "$REPO_DIR/.venv/bin/stray-ai-report" \
  --visit "\$VISIT_FILE" \
  --state "$DATA_DIR/agents/stray-001/state.json" \
  --output-dir "$DATA_DIR/reports"; then
  echo "Visit completed, but HTML report generation failed." >&2
fi
EOF
chmod 750 "$DATA_DIR/run-first-visitor.sh"

cat > "$DATA_DIR/generate-latest-report.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$REPO_DIR/.venv/bin/stray-ai-report" \
  --visits-dir "$DATA_DIR/agents/stray-001/visits" \
  --state "$DATA_DIR/agents/stray-001/state.json" \
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

"$REPO_DIR/.venv/bin/python" -m pytest "$REPO_DIR/tests"

echo "Devbox habitat prepared."
echo "Repository: $REPO_DIR"
echo "Persistent data: $DATA_DIR"
echo "Latest report: $DATA_DIR/reports/latest.html"
echo "First EFP visit: $DATA_DIR/visit-eternal-free-party.sh"
