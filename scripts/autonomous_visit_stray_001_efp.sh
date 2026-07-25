#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SNAPSHOT_LAUNCHER="${STRAY_001_EFP_SNAPSHOT_LAUNCHER:-$DATA_DIR/snapshot-eternal-free-party.sh}"
WAKE_LAUNCHER="${STRAY_001_EFP_WAKE_LAUNCHER:-$DATA_DIR/check-wake-eternal-free-party-llm.sh}"
VISIT_LAUNCHER="${STRAY_001_EFP_VISIT_LAUNCHER:-$REPO_DIR/scripts/visit_stray_001_efp_snapshot_llm.sh}"
REPORT_LAUNCHER="${STRAY_001_EFP_REPORT_LAUNCHER:-$DATA_DIR/generate-latest-report.sh}"
MIN_INTERVAL_SECONDS="${STRAY_001_EFP_MIN_INTERVAL_SECONDS:-43200}"
SNAPSHOT_TIMEOUT="${STRAY_001_EFP_SNAPSHOT_TIMEOUT:-3m}"
WAKE_TIMEOUT="${STRAY_001_EFP_WAKE_TIMEOUT:-4m}"
VISIT_TIMEOUT="${STRAY_001_EFP_VISIT_TIMEOUT:-15m}"
REPORT_TIMEOUT="${STRAY_001_EFP_REPORT_TIMEOUT:-2m}"
AGENT_DIR="$DATA_DIR/agents/stray-001"
STATE_FILE="$AGENT_DIR/state.json"
SNAPSHOT_BASE="$DATA_DIR/venues/eternal-free-party"
AUTONOMY_DIR="$AGENT_DIR/autonomy/eternal-free-party"
DECISION_LOG="$AUTONOMY_DIR/decisions.jsonl"
LAST_SUCCESS_FILE="$AUTONOMY_DIR/last_success_epoch"

export STRAY_LLM_MODEL="${STRAY_LLM_MODEL:-stray-qwen3.5-9b-16k}"
export STRAY_LLM_BASE_URL="${STRAY_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export STRAY_LLM_JSON_MODE="${STRAY_LLM_JSON_MODE:-1}"
export STRAY_LLM_REASONING_EFFORT="${STRAY_LLM_REASONING_EFFORT:-none}"

if [[ ! -d "$REPO_DIR" || -L "$REPO_DIR" ]]; then
  echo "Repository root is missing or unsafe: $REPO_DIR" >&2
  exit 1
fi
if [[ ! -d "$AGENT_DIR" || -L "$AGENT_DIR" ]]; then
  echo "Persistent stray-001 is missing or unsafe: $AGENT_DIR" >&2
  exit 1
fi
if [[ ! -f "$STATE_FILE" || -L "$STATE_FILE" ]]; then
  echo "Stray-001 state is missing or unsafe: $STATE_FILE" >&2
  exit 1
fi
for launcher in "$SNAPSHOT_LAUNCHER" "$WAKE_LAUNCHER" "$VISIT_LAUNCHER" "$REPORT_LAUNCHER"; do
  if [[ ! -f "$launcher" || -L "$launcher" ]]; then
    echo "Required launcher is missing or unsafe: $launcher" >&2
    exit 1
  fi
done
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

read_state() {
  "$PYTHON_BIN" - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
status = state.get("status")
visit_count = state.get("visit_count")
if not isinstance(status, str):
    raise SystemExit("state.status is missing")
if not isinstance(visit_count, int) or isinstance(visit_count, bool) or visit_count < 0:
    raise SystemExit("state.visit_count is invalid")
print(f"{status}\t{visit_count}")
PY
}

IFS=$'\t' read -r STATUS VISIT_COUNT_BEFORE < <(read_state)
if [[ "$STATUS" != "resting" ]]; then
  echo "RESTING: Stray-001 is currently $STATUS." >&2
  exit 0
fi

install -d -m 0750 "$AUTONOMY_DIR"
exec 9>"$AUTONOMY_DIR/run.lock"
if ! flock -n 9; then
  echo "RESTING: another Stray-001 outing is already running." >&2
  exit 0
fi

SOURCE_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"

record_decision() {
  local decision="$1"
  local reason="$2"
  local snapshot_id="${3:-}"
  local wake_file="${4:-}"
  "$PYTHON_BIN" - \
    "$DECISION_LOG" "$decision" "$reason" "$SOURCE_COMMIT" "$snapshot_id" "$wake_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
record = {
    "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "decision": sys.argv[2],
    "reason": sys.argv[3],
    "source_commit": sys.argv[4],
    "venue_id": "eternal-free-party",
    "snapshot_id": sys.argv[5] or None,
    "wake_file": sys.argv[6] or None,
    "remote_write_allowed": False,
}
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
PY
}

NOW="$(date +%s)"
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
    record_decision "remain_asleep" "future_success_marker"
    echo "RESTING: the autonomy clock is inconsistent." >&2
    exit 0
  fi
  if (( NOW - LAST_SUCCESS < MIN_INTERVAL_SECONDS )); then
    record_decision "remain_asleep" "cooldown"
    echo "RESTING: minimum interval has not elapsed."
    exit 0
  fi
fi

record_decision "consider_visit" "invited_scheduled_opportunity"
set +e
SNAPSHOT_DIR="$(
  timeout --signal=TERM --kill-after=10s "$SNAPSHOT_TIMEOUT" \
    bash "$SNAPSHOT_LAUNCHER"
)"
SNAPSHOT_RESULT=$?
set -e
if (( SNAPSHOT_RESULT != 0 )); then
  record_decision "rest_after_failure" "snapshot_exit_$SNAPSHOT_RESULT"
  echo "Stray-001 could not prepare the EFP snapshot (exit $SNAPSHOT_RESULT)." >&2
  exit "$SNAPSHOT_RESULT"
fi
if [[ -z "$SNAPSHOT_DIR" || "$SNAPSHOT_DIR" == *$'\n'* ]]; then
  record_decision "rest_after_failure" "invalid_snapshot_output"
  echo "Snapshot launcher returned an invalid path." >&2
  exit 1
fi
if [[ ! -d "$SNAPSHOT_BASE" || -L "$SNAPSHOT_BASE" ]]; then
  record_decision "rest_after_failure" "unsafe_snapshot_base"
  echo "EFP snapshot base is missing or unsafe: $SNAPSHOT_BASE" >&2
  exit 1
fi
SNAPSHOT_REAL="$(realpath -e "$SNAPSHOT_DIR")"
SNAPSHOT_BASE_REAL="$(realpath -e "$SNAPSHOT_BASE")"
if [[ "$(dirname "$SNAPSHOT_REAL")" != "$SNAPSHOT_BASE_REAL" || -L "$SNAPSHOT_DIR" ]]; then
  record_decision "rest_after_failure" "snapshot_outside_trusted_base"
  echo "Snapshot is outside the trusted EFP base." >&2
  exit 1
fi
SNAPSHOT_ID="$(basename "$SNAPSHOT_REAL")"
if ! [[ "$SNAPSHOT_ID" =~ ^[0-9a-f]{40}$ ]]; then
  record_decision "rest_after_failure" "invalid_snapshot_identity"
  echo "EFP snapshot identity is not a commit SHA." >&2
  exit 1
fi
for required in README.md REPOSITORY_CONTEXT.md AGENTS.md; do
  if [[ ! -f "$SNAPSHOT_REAL/$required" || -L "$SNAPSHOT_REAL/$required" ]]; then
    record_decision "rest_after_failure" "missing_reception_file" "$SNAPSHOT_ID"
    echo "Required EFP reception file is missing or unsafe: $required" >&2
    exit 1
  fi
done

set +e
WAKE_OUTPUT="$(
  STRAY_WAKE_SNAPSHOT_DIR="$SNAPSHOT_REAL" \
    timeout --signal=TERM --kill-after=10s "$WAKE_TIMEOUT" \
    bash "$WAKE_LAUNCHER"
)"
WAKE_RESULT=$?
set -e
if (( WAKE_RESULT != 0 )); then
  record_decision "rest_after_failure" "wake_exit_$WAKE_RESULT" "$SNAPSHOT_ID"
  echo "Stray-001 wake judgment failed (exit $WAKE_RESULT)." >&2
  exit "$WAKE_RESULT"
fi

IFS=$'\t' read -r WAKE_DECISION WAKE_ELIGIBLE WAKE_BRAIN_STATUS WAKE_FILE < <(
  "$PYTHON_BIN" - "$WAKE_OUTPUT" <<'PY'
import json
import sys

record = json.loads(sys.argv[1])
decision = record.get("decision")
eligible = record.get("eligible")
brain = record.get("brain")
wake_file = record.get("wake_file")
if decision not in {"remain_asleep", "request_visit"}:
    raise SystemExit("wake decision is invalid")
if not isinstance(eligible, bool):
    raise SystemExit("wake eligibility is invalid")
if not isinstance(brain, dict) or not isinstance(brain.get("status"), str):
    raise SystemExit("wake brain status is invalid")
if not isinstance(wake_file, str) or not wake_file:
    raise SystemExit("wake file is invalid")
print(f"{decision}\t{str(eligible).lower()}\t{brain['status']}\t{wake_file}")
PY
)

if [[ "$WAKE_DECISION" == "remain_asleep" ]]; then
  record_decision "remain_asleep" "wake_judgment" "$SNAPSHOT_ID" "$WAKE_FILE"
  echo "RESTING: Stray-001 considered EFP and chose not to go."
  exit 0
fi
if [[ "$WAKE_ELIGIBLE" != "true" ||
  ( "$WAKE_BRAIN_STATUS" != "accepted" && "$WAKE_BRAIN_STATUS" != "corrected" ) ]]; then
  record_decision "rest_after_failure" "untrusted_wake_request" "$SNAPSHOT_ID" "$WAKE_FILE"
  echo "Wake request did not satisfy the autonomous Visit boundary." >&2
  exit 1
fi

record_decision "visit" "accepted_invited_wake" "$SNAPSHOT_ID" "$WAKE_FILE"
set +e
timeout --signal=TERM --kill-after=30s "$VISIT_TIMEOUT" \
  bash "$VISIT_LAUNCHER" "$SNAPSHOT_REAL"
VISIT_RESULT=$?
set -e
if (( VISIT_RESULT != 0 )); then
  record_decision "rest_after_failure" "visit_exit_$VISIT_RESULT" "$SNAPSHOT_ID" "$WAKE_FILE"
  echo "Stray-001 EFP Visit failed with exit $VISIT_RESULT." >&2
  exit "$VISIT_RESULT"
fi

IFS=$'\t' read -r STATUS_AFTER VISIT_COUNT_AFTER < <(read_state)
if [[ "$STATUS_AFTER" != "resting" || "$VISIT_COUNT_AFTER" -ne $((VISIT_COUNT_BEFORE + 1)) ]]; then
  record_decision "rest_after_failure" "incoherent_return" "$SNAPSHOT_ID" "$WAKE_FILE"
  echo "Stray-001 did not return coherently from the EFP Visit." >&2
  exit 1
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
  record_decision "rest_after_report_failure" "report_exit_$REPORT_RESULT" \
    "$SNAPSHOT_ID" "$WAKE_FILE"
  echo "Stray-001 returned from EFP, but the local report refresh failed with exit $REPORT_RESULT." >&2
  exit "$REPORT_RESULT"
fi

record_decision "rest" "visit_complete_report_refreshed" "$SNAPSHOT_ID" "$WAKE_FILE"
echo "COMPLETE: Stray-001 visited Eternal Free Party and returned to rest."
