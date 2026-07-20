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
  "$DATA_DIR/venues" \
  "$DATA_DIR/outbox/traces" \
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
ENTRANCE="${STRAY_ENTRANCE:-$DATA_DIR/venues/README.md}"
if [[ ! -f "$ENTRANCE" ]]; then
  echo "Entrance not found: $ENTRANCE" >&2
  echo "Place a bounded venue under $DATA_DIR/venues or set STRAY_ENTRANCE." >&2
  exit 1
fi
exec "$REPO_DIR/.venv/bin/stray-ai" \
  --agent "$DATA_DIR/agents/stray-001" \
  --local-root "$DATA_DIR/venues" \
  --entrance "$ENTRANCE" \
  --outbox "$DATA_DIR/outbox/traces" \
  "\$@"
EOF
chmod 750 "$DATA_DIR/run-first-visitor.sh"

"$REPO_DIR/.venv/bin/python" -m pytest "$REPO_DIR/tests"

echo "Devbox habitat prepared."
echo "Repository: $REPO_DIR"
echo "Persistent data: $DATA_DIR"
echo "Next: place a bounded venue under $DATA_DIR/venues and run $DATA_DIR/run-first-visitor.sh"