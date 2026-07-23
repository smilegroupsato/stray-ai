#!/usr/bin/env bash
set -euo pipefail

if [[ "$(hostname -s)" != "devbox" ]]; then
  echo "This helper may run only on devbox." >&2
  exit 1
fi

REPO_ROOT="/srv/sgos/repos/stray-ai"
BOARD="$REPO_ROOT/registry/current_board.yml"
AGENT_DIR="/srv/sgos/data/stray-ai/agents/stray-001"
REPORT_ROOT="/srv/sgos/data/stray-ai/reports"
PYTHON="$REPO_ROOT/.venv/bin/python"
OUTPUT="$REPORT_ROOT/current/index.html"

[[ -x "$PYTHON" ]] || { echo "Missing virtualenv Python: $PYTHON" >&2; exit 1; }
[[ -f "$BOARD" ]] || { echo "Missing Current Board source: $BOARD" >&2; exit 1; }
[[ -d "$AGENT_DIR" ]] || { echo "Missing agent directory: $AGENT_DIR" >&2; exit 1; }
[[ -d "$REPORT_ROOT" ]] || { echo "Missing report root: $REPORT_ROOT" >&2; exit 1; }

cd "$REPO_ROOT"

"$PYTHON" -m stray_ai.current_board \
  --board "$BOARD" \
  --agent "$AGENT_DIR" \
  --report-root "$REPORT_ROOT"

[[ -f "$OUTPUT" ]] || { echo "Current Board HTML was not published." >&2; exit 1; }

if grep -Eiq '/srv/|snapshot_root|brain_command|<button|<form|<script|javascript:|file://' "$OUTPUT"; then
  echo "Published Current Board failed the static safety scan." >&2
  exit 1
fi

if find "$REPORT_ROOT/current" -maxdepth 1 -type f \( -name '*.json' -o -name '*.jsonl' \) -print -quit | grep -q .; then
  echo "JSON-like files must not be published in the Current Board directory." >&2
  exit 1
fi

printf '%s\n' \
  "Published read-only Stray AI Current Board:" \
  "  LAN:       http://192.168.1.20/stray-ai/current/index.html" \
  "  Tailscale: http://100.79.124.53/stray-ai/current/index.html" \
  "No wake check, Request action, snapshot, Visit, report regeneration, or scheduler was invoked."
