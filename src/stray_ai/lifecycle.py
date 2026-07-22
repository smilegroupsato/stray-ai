from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .memory_records import migrate_memory_records

_JST = ZoneInfo("Asia/Tokyo")
_FATIGUE_RECOVERY_PER_HOUR = 0.04
_LEGACY_MEMORY_BLOCK = (
    "No place has yet become a memory.\n\n"
    "The visitor has not completed its first visit."
)
_MEMORY_PREAMBLE = (
    "Memories are kept as dated observations. "
    "Silence and uncertainty may remain part of the record."
)


def _clamp_fatigue(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return min(1.0, max(0.0, number))


def migrate_memory(path: Path) -> bool:
    if not path.exists():
        path.write_text(f"# Memory\n\n{_MEMORY_PREAMBLE}\n", encoding="utf-8")
        return True

    original = path.read_text(encoding="utf-8")
    migrated = original.replace(_LEGACY_MEMORY_BLOCK, _MEMORY_PREAMBLE)
    if migrated == original:
        return False
    path.write_text(migrated, encoding="utf-8")
    return True


def _visit_records(agent_dir: Path) -> list[dict[str, Any]]:
    visits_dir = agent_dir / "visits"
    records: list[dict[str, Any]] = []
    if not visits_dir.exists():
        return records
    for path in sorted(visits_dir.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _final_location(record: dict[str, Any]) -> str | None:
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    final = steps[-1]
    if not isinstance(final, dict):
        return None
    location = final.get("location")
    return str(location) if location else None


def migrate_state(agent_dir: Path) -> bool:
    path = agent_dir / "state.json"
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}
    if not isinstance(state, dict):
        state = {}

    original = json.dumps(state, ensure_ascii=False, sort_keys=True)
    records = _visit_records(agent_dir)
    latest = records[-1] if records else None

    state["visit_count"] = max(int(state.get("visit_count", 0) or 0), len(records))
    state["llm_visit_count"] = sum(record.get("backend") == "command" for record in records)
    state["accepted_brain_visit_count"] = sum(
        record.get("backend") == "command"
        and any(
            isinstance(step, dict)
            and isinstance(step.get("brain"), dict)
            and step["brain"].get("status") in {"accepted", "corrected"}
            for step in record.get("steps", [])
        )
        for record in records
    )
    state["safe_exit_count"] = sum(
        record.get("exit_reason") == "brain_failed_safe_exit" for record in records
    )
    state["fatigue"] = _clamp_fatigue(state.get("fatigue", 0.0))
    state.setdefault("unresolved_impulses", [])
    if not isinstance(state["unresolved_impulses"], list):
        state["unresolved_impulses"] = []

    if latest:
        last_visit = latest.get("ended_at") or state.get("last_visit")
        state["status"] = "resting"
        state["current_location"] = None
        state["last_location"] = _final_location(latest) or state.get("last_location")
        state["last_visit"] = last_visit
        state.setdefault("rest_started_at", last_visit)
        state["last_exit_reason"] = latest.get("exit_reason")
        state["last_backend"] = latest.get("backend")
        state["last_model"] = latest.get("brain_model")
    else:
        state.setdefault("status", "unborn")
        state["current_location"] = None
        state.setdefault("last_location", None)
        state.setdefault("last_visit", None)
        state.setdefault("rest_started_at", None)
        state.setdefault("last_exit_reason", None)
        state.setdefault("last_backend", None)
        state.setdefault("last_model", None)

    migrated = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if migrated == original and path.exists():
        return False
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_agent(agent_dir: Path) -> dict[str, bool]:
    agent_dir.mkdir(parents=True, exist_ok=True)
    return {
        "memory_changed": migrate_memory(agent_dir / "memory.md"),
        "memory_records_changed": migrate_memory_records(agent_dir),
        "state_changed": migrate_state(agent_dir),
    }


def recovered_fatigue(
    fatigue: float,
    *,
    rest_started_at: str | None,
    now: datetime | None = None,
) -> float:
    value = _clamp_fatigue(fatigue)
    if not rest_started_at:
        return value
    try:
        started = datetime.fromisoformat(rest_started_at)
    except ValueError:
        return value
    if started.tzinfo is None:
        started = started.replace(tzinfo=_JST)
    current = now or datetime.now(_JST)
    elapsed_hours = max(0.0, (current - started).total_seconds() / 3600)
    return _clamp_fatigue(value - elapsed_hours * _FATIGUE_RECOVERY_PER_HOUR)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="stray-ai-migrate")
    parser.add_argument("agent_dir", type=Path)
    args = parser.parse_args()
    result = migrate_agent(args.agent_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
