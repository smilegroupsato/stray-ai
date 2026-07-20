from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .lifecycle import recovered_fatigue

_JST = ZoneInfo("Asia/Tokyo")
_ALLOWED_DECISIONS = {"remain_asleep", "request_visit"}
_MAX_OBSERVATION_CHARACTERS = 360
_MAX_REASON_CHARACTERS = 240
_MAX_IMPULSE_CHARACTERS = 240
_MAX_MEMORY_EXCERPT_CHARACTERS = 4000
_DEFAULT_MINIMUM_REST_HOURS = 12.0
_DEFAULT_MAXIMUM_FATIGUE = 0.5


@dataclass(slots=True)
class WakePolicy:
    minimum_rest_hours: float = _DEFAULT_MINIMUM_REST_HOURS
    maximum_fatigue_to_consider: float = _DEFAULT_MAXIMUM_FATIGUE
    max_new_impulses_per_check: int = 1


@dataclass(slots=True)
class WakeDecision:
    decision: str
    observation: str = ""
    reason: str = ""
    impulses: list[str] | None = None
    status: str = "accepted"
    error: str | None = None

    def __post_init__(self) -> None:
        self.impulses = self.impulses or []


def _now() -> datetime:
    return datetime.now(_JST)


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _bounded_float(value: Any, default: float, *, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, number))


def _load_policy(agent_dir: Path) -> WakePolicy:
    profile_path = agent_dir / "profile.yml"
    data: dict[str, Any] = {}
    if profile_path.exists():
        loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    wake = data.get("wake") if isinstance(data.get("wake"), dict) else {}
    return WakePolicy(
        minimum_rest_hours=_bounded_float(
            wake.get("minimum_rest_hours"),
            _DEFAULT_MINIMUM_REST_HOURS,
            low=0.0,
            high=24.0 * 30.0,
        ),
        maximum_fatigue_to_consider=_bounded_float(
            wake.get("maximum_fatigue_to_consider"),
            _DEFAULT_MAXIMUM_FATIGUE,
            low=0.0,
            high=1.0,
        ),
        max_new_impulses_per_check=max(
            0,
            min(1, int(wake.get("max_new_impulses_per_check", 1) or 0)),
        ),
    )


def _load_state(agent_dir: Path) -> dict[str, Any]:
    path = agent_dir / "state.json"
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("state.json must contain a JSON object")
    return value


def _save_state(agent_dir: Path, state: dict[str, Any]) -> None:
    (agent_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _memory_excerpt(agent_dir: Path) -> str:
    path = agent_dir / "memory.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[
        -_MAX_MEMORY_EXCERPT_CHARACTERS:
    ]


def _elapsed_rest_hours(rest_started_at: str | None, now: datetime) -> float:
    if not rest_started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(rest_started_at)
    except ValueError:
        return 0.0
    if started.tzinfo is None:
        started = started.replace(tzinfo=_JST)
    return max(0.0, (now - started).total_seconds() / 3600.0)


def _latest_snapshot_id(agent_dir: Path) -> str | None:
    visits_dir = agent_dir / "visits"
    if not visits_dir.exists():
        return None
    for path in reversed(sorted(visits_dir.glob("*.json"))):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict):
            continue
        entrance = value.get("entrance")
        if entrance:
            return _clean_text(Path(str(entrance)).parent.name, 160) or None
    return None


def normalize_wake_decision(value: Any) -> WakeDecision:
    if not isinstance(value, dict):
        raise ValueError("wake output must be a JSON object")
    decision = value.get("decision")
    if decision not in _ALLOWED_DECISIONS:
        raise ValueError("wake decision is not allowed")

    impulses_value = value.get("impulses", [])
    if not isinstance(impulses_value, list):
        raise ValueError("wake impulses must be a list")
    impulses = list(
        dict.fromkeys(
            _clean_text(item, _MAX_IMPULSE_CHARACTERS)
            for item in impulses_value
            if isinstance(item, str) and item.strip()
        )
    )[:1]
    if decision == "remain_asleep":
        impulses = []

    return WakeDecision(
        decision=decision,
        observation=_clean_text(value.get("observation"), _MAX_OBSERVATION_CHARACTERS),
        reason=_clean_text(value.get("reason"), _MAX_REASON_CHARACTERS),
        impulses=impulses,
    )


def _rejected_decision(error: str) -> WakeDecision:
    return WakeDecision(
        decision="remain_asleep",
        observation="The wake judgment was unavailable, so the visitor remained asleep.",
        reason="fail-closed",
        status="rejected",
        error=_clean_text(error, 360),
    )


class WakeCommandBrain:
    protocol = "stray-wake-v1"

    def __init__(self, command: list[str], *, label: str | None, timeout_seconds: float = 45.0):
        if not command:
            raise ValueError("wake brain command is required")
        self.command = command
        self.label = label
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 600.0))

    def decide(self, payload: dict[str, Any]) -> WakeDecision:
        try:
            result = subprocess.run(
                self.command,
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return _rejected_decision("wake brain adapter timed out")
        except OSError as exc:
            return _rejected_decision(f"wake brain adapter could not start: {exc}")

        if result.returncode != 0:
            detail = _clean_text(result.stderr, 240) or f"exit status {result.returncode}"
            return _rejected_decision(f"wake brain adapter failed: {detail}")
        try:
            return normalize_wake_decision(json.loads(result.stdout))
        except (json.JSONDecodeError, ValueError) as exc:
            return _rejected_decision(f"invalid wake brain output: {exc}")


def _next_record_path(directory: Path, checked_at: datetime) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = checked_at.strftime("%Y-%m-%d_%H%M%S")
    candidate = directory / f"{stem}.json"
    suffix = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{suffix:02d}.json"
        suffix += 1
    return candidate


def run_wake_check(
    *,
    agent_dir: Path,
    candidate_snapshot_id: str,
    previous_snapshot_id: str | None = None,
    brain: WakeCommandBrain | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    checked_at = now or _now()
    policy = _load_policy(agent_dir)
    state = _load_state(agent_dir)

    candidate_id = _clean_text(candidate_snapshot_id, 160)
    if not candidate_id:
        raise ValueError("candidate snapshot id is required")
    previous_id = _clean_text(previous_snapshot_id, 160) if previous_snapshot_id else None
    previous_id = previous_id or _latest_snapshot_id(agent_dir)

    rest_started_at = state.get("rest_started_at")
    rest_started_text = str(rest_started_at) if rest_started_at else None
    elapsed_hours = _elapsed_rest_hours(rest_started_text, checked_at)
    fatigue = recovered_fatigue(
        float(state.get("fatigue", 0.0) or 0.0),
        rest_started_at=rest_started_text,
        now=checked_at,
    )
    venue_changed = bool(previous_id and previous_id != candidate_id)

    blockers: list[str] = []
    if state.get("status") != "resting":
        blockers.append("visitor is not resting")
    if elapsed_hours < policy.minimum_rest_hours:
        blockers.append("minimum rest time has not elapsed")
    if fatigue > policy.maximum_fatigue_to_consider:
        blockers.append("fatigue remains above the wake threshold")
    eligible = not blockers

    brain_status = "not_invoked"
    brain_error: str | None = None
    model = brain.label if brain else None
    protocol = brain.protocol if brain else "deterministic-wake-gate-v1"

    if not eligible:
        decision = WakeDecision(
            decision="remain_asleep",
            observation="; ".join(blockers),
            reason="deterministic body gate",
        )
        source = "deterministic_gate"
    elif brain is None:
        decision = WakeDecision(
            decision="remain_asleep",
            observation="The body was eligible, but no wake brain was invoked.",
            reason="deterministic default",
        )
        source = "deterministic_default"
    else:
        payload = {
            "visitor": {
                "memory_excerpt": _memory_excerpt(agent_dir),
                "unresolved_impulses": [
                    _clean_text(item, _MAX_IMPULSE_CHARACTERS)
                    for item in state.get("unresolved_impulses", [])
                    if isinstance(item, str) and item.strip()
                ][:8],
            },
            "rest": {
                "elapsed_hours": round(elapsed_hours, 4),
                "recovered_fatigue": round(fatigue, 4),
                "minimum_rest_hours": policy.minimum_rest_hours,
                "maximum_fatigue_to_consider": policy.maximum_fatigue_to_consider,
            },
            "venue": {
                "previous_snapshot_id": previous_id,
                "candidate_snapshot_id": candidate_id,
                "changed": venue_changed,
                "content_was_not_read": True,
            },
            "output_contract": {
                "decisions": sorted(_ALLOWED_DECISIONS),
                "max_new_impulses": policy.max_new_impulses_per_check,
                "wake_request_does_not_start_a_visit": True,
            },
        }
        decision = brain.decide(payload)
        brain_status = decision.status
        brain_error = decision.error
        source = "command_brain"

    added_impulses: list[str] = []
    if (
        decision.decision == "request_visit"
        and decision.status in {"accepted", "corrected"}
        and policy.max_new_impulses_per_check > 0
    ):
        existing = [
            _clean_text(item, _MAX_IMPULSE_CHARACTERS)
            for item in state.get("unresolved_impulses", [])
            if isinstance(item, str) and item.strip()
        ]
        for impulse in decision.impulses or []:
            if impulse and impulse not in existing:
                existing.append(impulse)
                added_impulses.append(impulse)
                break
        state["unresolved_impulses"] = existing
        state["status"] = "resting"
        state["current_location"] = None
        if added_impulses:
            _save_state(agent_dir, state)

    wake_file = _next_record_path(agent_dir / "wake_checks", checked_at)
    record: dict[str, Any] = {
        "agent_id": state.get("id") or agent_dir.name,
        "checked_at": checked_at.isoformat(timespec="seconds"),
        "source": source,
        "eligible": eligible,
        "blockers": blockers,
        "policy": {
            "minimum_rest_hours": policy.minimum_rest_hours,
            "maximum_fatigue_to_consider": policy.maximum_fatigue_to_consider,
        },
        "rest": {
            "elapsed_hours": round(elapsed_hours, 4),
            "recovered_fatigue": round(fatigue, 4),
        },
        "venue": {
            "previous_snapshot_id": previous_id,
            "candidate_snapshot_id": candidate_id,
            "changed": venue_changed,
            "content_was_not_read": True,
        },
        "brain": {
            "status": brain_status,
            "model": model,
            "protocol": protocol,
            "error": brain_error,
        },
        "decision": decision.decision,
        "observation": decision.observation,
        "reason": decision.reason,
        "impulses_added": added_impulses,
        "state_status_after": state.get("status"),
        "current_location_after": state.get("current_location"),
        "wake_file": str(wake_file),
    }
    wake_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-wake")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--candidate-snapshot-id", required=True)
    parser.add_argument("--previous-snapshot-id")
    parser.add_argument("--brain", choices=["deterministic", "command"], default="deterministic")
    parser.add_argument("--brain-command")
    parser.add_argument("--brain-label")
    parser.add_argument("--brain-timeout", type=float, default=45.0)
    args = parser.parse_args()

    brain: WakeCommandBrain | None = None
    if args.brain == "command":
        if not args.brain_command:
            parser.error("--brain-command is required for command brain")
        brain = WakeCommandBrain(
            shlex.split(args.brain_command),
            label=args.brain_label,
            timeout_seconds=args.brain_timeout,
        )

    result = run_wake_check(
        agent_dir=args.agent,
        candidate_snapshot_id=args.candidate_snapshot_id,
        previous_snapshot_id=args.previous_snapshot_id,
        brain=brain,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
