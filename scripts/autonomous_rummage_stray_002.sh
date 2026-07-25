#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUMMAGE_LAUNCHER="${STRAY_AUTONOMY_RUMMAGE_LAUNCHER:-$REPO_DIR/scripts/rummage_stray_002_llm.sh}"
MIN_INTERVAL_SECONDS="${STRAY_AUTONOMY_MIN_INTERVAL_SECONDS:-72000}"
RUN_TIMEOUT="${STRAY_AUTONOMY_RUN_TIMEOUT:-12m}"
REPORT_LAUNCHER="${STRAY_AUTONOMY_REPORT_LAUNCHER:-$DATA_DIR/generate-latest-report.sh}"
REPORT_TIMEOUT="${STRAY_AUTONOMY_REPORT_TIMEOUT:-2m}"
AGENT_DIR="$DATA_DIR/agents/stray-002"
STATE_FILE="$AGENT_DIR/state.json"
AUTONOMY_DIR="$AGENT_DIR/autonomy"
DECISION_LOG="$AUTONOMY_DIR/decisions.jsonl"
LAST_SUCCESS_FILE="$AUTONOMY_DIR/last_success_epoch"

if [[ ! -d "$REPO_DIR" || -L "$REPO_DIR" ]]; then
  echo "Repository root is missing or unsafe: $REPO_DIR" >&2
  exit 1
fi
if [[ ! -d "$AGENT_DIR" || -L "$AGENT_DIR" ]]; then
  echo "Persistent stray-002 is missing or unsafe: $AGENT_DIR" >&2
  exit 1
fi
if [[ ! -f "$STATE_FILE" || -L "$STATE_FILE" ]]; then
  echo "Stray-002 state is missing or unsafe: $STATE_FILE" >&2
  exit 1
fi
if [[ ! -f "$RUMMAGE_LAUNCHER" || -L "$RUMMAGE_LAUNCHER" ]]; then
  echo "Rummage launcher is missing or unsafe: $RUMMAGE_LAUNCHER" >&2
  exit 1
fi
if [[ ! -f "$REPORT_LAUNCHER" || -L "$REPORT_LAUNCHER" ]]; then
  echo "Report launcher is missing or unsafe: $REPORT_LAUNCHER" >&2
  exit 1
fi
if ! [[ "$MIN_INTERVAL_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "Minimum interval must be a non-negative integer." >&2
  exit 1
fi

BRANCH="$(git -C "$REPO_DIR" symbolic-ref --quiet --short HEAD || true)"
if [[ "$BRANCH" != "main" ]]; then
  echo "RESTING: repository is not on main ($BRANCH)." >&2
  exit 0
fi
if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
  echo "RESTING: repository working tree is not clean." >&2
  exit 0
fi

STATUS="$(
  "$PYTHON_BIN" - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
status = state.get("status")
if not isinstance(status, str):
    raise SystemExit("state.status is missing")
print(status)
PY
)"
if [[ "$STATUS" != "resting" ]]; then
  echo "RESTING: Stray-002 is currently $STATUS." >&2
  exit 0
fi

install -d -m 0750 "$AUTONOMY_DIR"
exec 9>"$AUTONOMY_DIR/run.lock"
if ! flock -n 9; then
  echo "RESTING: another Stray-002 rummage is already running." >&2
  exit 0
fi

record_decision() {
  local decision="$1"
  local reason="$2"
  local source_commit="$3"
  local recorded_at
  recorded_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf \
    '{"recorded_at":"%s","decision":"%s","reason":"%s","source_commit":"%s"}\n' \
    "$recorded_at" "$decision" "$reason" "$source_commit" >>"$DECISION_LOG"
}

NOW="$(date +%s)"
SOURCE_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
if [[ -e "$LAST_SUCCESS_FILE" ]]; then
  if [[ ! -f "$LAST_SUCCESS_FILE" || -L "$LAST_SUCCESS_FILE" ]]; then
    echo "Autonomy success marker is unsafe: $LAST_SUCCESS_FILE" >&2
    exit 1
  fi
  LAST_SUCCESS="$(<"$LAST_SUCCESS_FILE")"
  if ! [[ "$LAST_SUCCESS" =~ ^[0-9]+$ ]]; then
    echo "Autonomy success marker is invalid." >&2
    exit 1
  fi
  if (( LAST_SUCCESS > NOW )); then
    record_decision "remain_asleep" "future_success_marker" "$SOURCE_COMMIT"
    echo "RESTING: the autonomy clock is inconsistent." >&2
    exit 0
  fi
  if (( NOW - LAST_SUCCESS < MIN_INTERVAL_SECONDS )); then
    record_decision "remain_asleep" "cooldown" "$SOURCE_COMMIT"
    echo "RESTING: minimum interval has not elapsed."
    exit 0
  fi
fi

record_decision "rummage" "scheduled_opportunity" "$SOURCE_COMMIT"
set +e
timeout --signal=TERM --kill-after=30s "$RUN_TIMEOUT" \
  bash "$RUMMAGE_LAUNCHER"
RESULT=$?
set -e

if (( RESULT != 0 )); then
  record_decision "rest_after_failure" "rummage_exit_$RESULT" "$SOURCE_COMMIT"
  echo "Stray-002 autonomous rummage failed with exit $RESULT." >&2
  exit "$RESULT"
fi

SUCCESS_EPOCH="$(date +%s)"
TMP_MARKER="$AUTONOMY_DIR/.last_success_epoch.$$"
trap 'rm -f "$TMP_MARKER"' EXIT
printf '%s\n' "$SUCCESS_EPOCH" >"$TMP_MARKER"
chmod 0640 "$TMP_MARKER"
mv -f "$TMP_MARKER" "$LAST_SUCCESS_FILE"
trap - EXIT
set +e
timeout --signal=TERM --kill-after=10s "$REPORT_TIMEOUT" \
  bash "$REPORT_LAUNCHER"
REPORT_RESULT=$?
set -e

if (( REPORT_RESULT != 0 )); then
  record_decision "rest_after_report_failure" "report_exit_$REPORT_RESULT" "$SOURCE_COMMIT"
  echo "Stray-002 rummaged successfully, but the local individual page refresh failed with exit $REPORT_RESULT." >&2
  exit "$REPORT_RESULT"
fi

record_decision "rest" "rummage_complete_report_refreshed" "$SOURCE_COMMIT"
echo "COMPLETE: Stray-002 rummaged once, refreshed its local individual page, and returned to rest."
