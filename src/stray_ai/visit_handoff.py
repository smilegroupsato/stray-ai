from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

_JST = ZoneInfo("Asia/Tokyo")
_SCHEMA = "stray-visit-request-v1"
_ALLOWED_BRAIN_STATUSES = {"accepted", "corrected"}
_VENUE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


class VisitHandoffError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(_JST)


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisitHandoffError(f"{label} is not readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VisitHandoffError(f"{label} must contain a JSON object")
    return value


def _relative_member(path: Path, root: Path, *, label: str) -> Path:
    if path.is_absolute():
        raise VisitHandoffError(f"{label} must be relative to the snapshot root")
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise VisitHandoffError(f"{label} escapes the snapshot root") from exc
    if not resolved.is_file():
        raise VisitHandoffError(f"{label} is not an existing file")
    if resolved.suffix.lower() not in _TEXT_SUFFIXES:
        raise VisitHandoffError(f"{label} is not a supported text page")
    return resolved


def _wake_record(agent_dir: Path, wake_file: Path) -> tuple[Path, dict[str, Any], str]:
    wake_root = (agent_dir / "wake_checks").resolve()
    resolved = wake_file.resolve()
    try:
        resolved.relative_to(wake_root)
    except ValueError as exc:
        raise VisitHandoffError("wake record must be inside the agent wake_checks directory") from exc
    if not resolved.is_file():
        raise VisitHandoffError("wake record does not exist")

    raw = resolved.read_bytes()
    record = _read_json_object(resolved, label="wake record")
    if record.get("eligible") is not True:
        raise VisitHandoffError("wake record is not eligible")
    if record.get("decision") != "request_visit":
        raise VisitHandoffError("wake record does not request a visit")
    brain = record.get("brain")
    if not isinstance(brain, dict) or brain.get("status") not in _ALLOWED_BRAIN_STATUSES:
        raise VisitHandoffError("wake request was not accepted by the bounded wake brain")
    if record.get("state_status_after") != "resting":
        raise VisitHandoffError("visitor was not resting after the wake judgment")
    if record.get("current_location_after") is not None:
        raise VisitHandoffError("visitor had a current location after the wake judgment")

    venue = record.get("venue")
    if not isinstance(venue, dict):
        raise VisitHandoffError("wake record has no bounded venue identity")
    candidate = venue.get("candidate_snapshot_id")
    if not isinstance(candidate, str) or not candidate.strip():
        raise VisitHandoffError("wake record has no candidate snapshot identity")
    return resolved, record, hashlib.sha256(raw).hexdigest()


def _profile(agent_dir: Path) -> tuple[str, int]:
    profile_path = agent_dir / "profile.yml"
    if not profile_path.is_file():
        raise VisitHandoffError("agent profile.yml does not exist")
    loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise VisitHandoffError("profile.yml must contain a mapping")
    agent_id = str(loaded.get("id") or agent_dir.name)
    movement = loaded.get("movement") if isinstance(loaded.get("movement"), dict) else {}
    try:
        max_places = int(movement.get("max_places_per_visit", 4))
    except (TypeError, ValueError) as exc:
        raise VisitHandoffError("max_places_per_visit is invalid") from exc
    return agent_id, max(1, min(max_places, 32))


def _existing_request(path: Path, expected: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    existing = _read_json_object(path, label="existing visit request")
    stable_fields = ("schema", "request_id", "agent_id", "source_wake", "source_wake_sha256", "venue")
    if any(existing.get(key) != expected.get(key) for key in stable_fields):
        raise VisitHandoffError("an incompatible request already exists for this wake record")
    if existing.get("status") != "pending_human_approval":
        raise VisitHandoffError("the existing request is no longer pending human approval")
    return existing


def prepare_visit_request(
    *,
    agent_dir: Path,
    wake_file: Path,
    venue_id: str,
    snapshot_root: Path,
    entrance: Path,
    arrival_path: list[Path] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    if not _VENUE_ID.fullmatch(venue_id):
        raise VisitHandoffError("venue id must use lowercase letters, digits, dot, underscore, or hyphen")

    source_wake, wake, wake_sha256 = _wake_record(agent_dir, wake_file)
    agent_id, max_places = _profile(agent_dir)
    wake_agent = wake.get("agent_id")
    if wake_agent not in {agent_id, agent_dir.name}:
        raise VisitHandoffError("wake record belongs to a different agent")

    root = snapshot_root.resolve()
    if not root.is_dir():
        raise VisitHandoffError("snapshot root is not an existing directory")
    candidate_id = str(wake["venue"]["candidate_snapshot_id"]).strip()
    if root.name != candidate_id:
        raise VisitHandoffError("snapshot directory name does not match the wake candidate identity")

    entrance_file = _relative_member(entrance, root, label="entrance")
    arrival_files = [
        _relative_member(path, root, label=f"arrival path {index}")
        for index, path in enumerate(arrival_path or [], start=1)
    ]
    route = [entrance_file, *arrival_files]
    if len(route) > max_places:
        raise VisitHandoffError("trusted route exceeds max_places_per_visit")
    if len(set(route)) != len(route):
        raise VisitHandoffError("trusted route contains duplicate pages")

    source_relative = source_wake.relative_to(agent_dir).as_posix()
    request_id = f"{source_wake.stem}-{wake_sha256[:12]}"
    request_dir = agent_dir / "visit_requests"
    request_file = request_dir / f"{request_id}.json"
    created_at = (now or _now()).isoformat(timespec="seconds")

    envelope: dict[str, Any] = {
        "schema": _SCHEMA,
        "request_id": request_id,
        "status": "pending_human_approval",
        "created_at": created_at,
        "agent_id": agent_id,
        "source_wake": source_relative,
        "source_wake_sha256": wake_sha256,
        "wake": {
            "checked_at": wake.get("checked_at"),
            "decision": wake.get("decision"),
            "observation": wake.get("observation"),
            "reason": wake.get("reason"),
            "impulses_added": wake.get("impulses_added", []),
        },
        "venue": {
            "venue_id": venue_id,
            "snapshot_id": candidate_id,
            "snapshot_root": str(root),
            "entrance": entrance_file.relative_to(root).as_posix(),
            "arrival_path": [path.relative_to(root).as_posix() for path in arrival_files],
        },
        "constraints": {
            "max_places": max_places,
            "venue_content_read": False,
            "visit_started": False,
            "human_approval_required": True,
            "automatic_execution_allowed": False,
        },
        "approval": {
            "approved_at": None,
            "approved_by": None,
        },
        "execution": {
            "started_at": None,
            "visit_file": None,
        },
    }

    existing = _existing_request(request_file, envelope)
    if existing is not None:
        return {"created": False, "request_file": str(request_file), "request": existing}

    request_dir.mkdir(parents=True, exist_ok=True)
    request_file.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"created": True, "request_file": str(request_file), "request": envelope}


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-prepare-visit")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--wake-record", type=Path, required=True)
    parser.add_argument("--venue-id", required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--entrance", type=Path, required=True)
    parser.add_argument("--arrival-path", type=Path, nargs="*", default=[])
    args = parser.parse_args()

    try:
        result = prepare_visit_request(
            agent_dir=args.agent,
            wake_file=args.wake_record,
            venue_id=args.venue_id,
            snapshot_root=args.snapshot_root,
            entrance=args.entrance,
            arrival_path=args.arrival_path,
        )
    except VisitHandoffError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
