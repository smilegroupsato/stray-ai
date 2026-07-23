from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .lifecycle import recovered_fatigue
from .wake import _elapsed_rest_hours, _latest_snapshot_id, _load_policy, _load_state

_JST = ZoneInfo("Asia/Tokyo")
_REGISTRY_SCHEMA = "0.1"
_RECORD_SCHEMA = "stray-wake-selection-v0"
_MAX_CANDIDATES = 8
_MAX_ENABLED_VENUES = 8
_MAX_IMPULSES = 8
_MAX_IMPULSE_CHARACTERS = 240
_MAX_OBSERVATION_CHARACTERS = 360
_MAX_REASON_CHARACTERS = 240
_SAFE_VENUE_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
_SAFE_SNAPSHOT_ID = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,158}[A-Za-z0-9])?")
_REASON_CODES = {
    "no_specific_reason",
    "rest_preferred",
    "tie_unresolved",
    "opaque_identity_changed",
    "unresolved_impulse",
    "comparison_unavailable",
}


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError("selector text fields must be strings")
    text = " ".join(value.split())
    if len(text) > limit:
        raise ValueError("selector text field is oversized")
    return text


@dataclass(slots=True)
class WakeSelectionDecision:
    decision: str
    selected_venue_id: str | None
    observation: str
    reason: str
    reason_code: str
    status: str = "accepted"
    error: str | None = None


def normalize_selection_decision(
    value: Any, *, candidate_venue_ids: set[str]
) -> WakeSelectionDecision:
    if not isinstance(value, dict):
        raise ValueError("selector output must be a JSON object")
    decision = value.get("decision")
    selected = value.get("selected_venue_id")
    reason_code = value.get("reason_code")
    if decision not in {"remain_asleep", "select_venue"}:
        raise ValueError("selector decision is not allowed")
    if reason_code not in _REASON_CODES:
        raise ValueError("selector reason code is not allowed")
    if decision == "remain_asleep" and selected is not None:
        raise ValueError("remain_asleep requires a null selected venue")
    if decision == "select_venue" and selected not in candidate_venue_ids:
        raise ValueError("selected venue is not an exact candidate ID")
    return WakeSelectionDecision(
        decision=decision,
        selected_venue_id=selected,
        observation=_clean_text(value.get("observation", ""), _MAX_OBSERVATION_CHARACTERS),
        reason=_clean_text(value.get("reason", ""), _MAX_REASON_CHARACTERS),
        reason_code=reason_code,
    )


def _rejected_decision(error: str) -> WakeSelectionDecision:
    return WakeSelectionDecision(
        decision="remain_asleep",
        selected_venue_id=None,
        observation="The selector was unavailable, so the visitor remained asleep.",
        reason="fail-closed selector rejection",
        reason_code="rest_preferred",
        status="rejected",
        error=" ".join(str(error).split())[:360],
    )


class WakeSelectorCommand:
    protocol = "stray-wake-selector-v0"

    def __init__(self, command: list[str], *, label: str | None, timeout_seconds: float = 45.0):
        if not command:
            raise ValueError("selector command is required")
        self.command = command
        self.label = label
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 600.0))

    def decide(
        self, payload: dict[str, Any], *, candidate_venue_ids: set[str]
    ) -> WakeSelectionDecision:
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
            return _rejected_decision("selector adapter timed out")
        except OSError as exc:
            return _rejected_decision(f"selector adapter could not start: {exc}")
        if result.returncode != 0:
            detail = " ".join(result.stderr.split())[:240] or f"exit status {result.returncode}"
            return _rejected_decision(f"selector adapter failed: {detail}")
        try:
            return normalize_selection_decision(
                json.loads(result.stdout), candidate_venue_ids=candidate_venue_ids
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return _rejected_decision(f"invalid selector output: {exc}")


def _safe_venue_id(value: Any) -> str:
    if not isinstance(value, str) or not _SAFE_VENUE_ID.fullmatch(value):
        raise ValueError("Venue ID must be a bounded safe lowercase slug")
    return value


def _safe_snapshot_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or value in {".", ".."}
        or not _SAFE_SNAPSHOT_ID.fullmatch(value)
    ):
        raise ValueError("snapshot ID must be one bounded safe path component")
    return value


def _load_registry(path: Path) -> tuple[dict[str, bool], str]:
    raw = path.read_bytes()
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise ValueError("registry root must be an object")
    if set(value) != {"schema_version", "venues"}:
        raise ValueError("registry contains unsupported fields")
    if str(value["schema_version"]) != _REGISTRY_SCHEMA:
        raise ValueError("registry schema is unsupported")
    entries = value["venues"]
    if not isinstance(entries, list):
        raise ValueError("registry venues must be a list")
    venues: dict[str, bool] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("registry Venue entry must be an object")
        if set(entry) != {"venue_id", "display_name", "selection_enabled"}:
            raise ValueError("registry Venue entry contains unsupported fields")
        venue_id = _safe_venue_id(entry["venue_id"])
        if venue_id in venues:
            raise ValueError("registry contains a duplicate Venue ID")
        if not isinstance(entry["display_name"], str) or not entry["display_name"].strip():
            raise ValueError("registry display_name must be non-empty text")
        if not isinstance(entry["selection_enabled"], bool):
            raise ValueError("registry selection_enabled must be boolean")
        venues[venue_id] = entry["selection_enabled"]
    if sum(venues.values()) > _MAX_ENABLED_VENUES:
        raise ValueError("registry enables too many Venues")
    return venues, hashlib.sha256(raw).hexdigest()


def _snapshot_directory(venues_root: Path, venue_id: str, snapshot_id: str) -> Path:
    directory = venues_root / venue_id / snapshot_id
    if directory.is_symlink():
        raise ValueError("snapshot directory must not be a symlink")
    if not directory.is_dir():
        raise ValueError("snapshot directory does not exist")
    expected_parent = (venues_root / venue_id).resolve()
    if directory.resolve().parent != expected_parent:
        raise ValueError("snapshot directory escapes its Venue root")
    return directory


def _construct_candidates(
    *,
    venues: dict[str, bool],
    venues_root: Path,
    explicit_candidates: list[str] | None,
    use_current_snapshots: bool,
) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
    if explicit_candidates and use_current_snapshots:
        raise ValueError("explicit candidates and current snapshots are mutually exclusive")
    candidates: list[tuple[str, str]] = []
    omissions: list[dict[str, str]] = []
    seen: set[str] = set()
    if explicit_candidates:
        if len(explicit_candidates) > _MAX_CANDIDATES:
            raise ValueError("candidate count exceeds the bounded maximum")
        for item in explicit_candidates:
            if not isinstance(item, str) or item.count("=") != 1:
                raise ValueError("candidate must use venue_id=snapshot_id")
            venue_raw, snapshot_raw = item.split("=", 1)
            venue_id = _safe_venue_id(venue_raw)
            snapshot_id = _safe_snapshot_id(snapshot_raw)
            if venue_id in seen:
                raise ValueError("candidate Venue IDs must be unique")
            if venue_id not in venues or not venues[venue_id]:
                raise ValueError("candidate Venue ID is unknown or disabled")
            _snapshot_directory(venues_root, venue_id, snapshot_id)
            seen.add(venue_id)
            candidates.append((venue_id, snapshot_id))
    elif use_current_snapshots:
        for venue_id in sorted(venue for venue, enabled in venues.items() if enabled):
            current = venues_root / venue_id / "current"
            if not current.is_symlink():
                omissions.append({"venue_id": venue_id, "reason": "usable current symlink absent"})
                continue
            try:
                raw_target = os.readlink(current)
                snapshot_id = _safe_snapshot_id(raw_target)
                _snapshot_directory(venues_root, venue_id, snapshot_id)
            except (OSError, ValueError):
                omissions.append({"venue_id": venue_id, "reason": "current symlink is unsafe"})
                continue
            candidates.append((venue_id, snapshot_id))
        if len(candidates) > _MAX_CANDIDATES:
            raise ValueError("candidate count exceeds the bounded maximum")
    return sorted(candidates), omissions


def _next_record_path(directory: Path, checked_at: datetime) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = checked_at.strftime("%Y-%m-%d_%H%M%S")
    path = directory / f"{stem}.json"
    suffix = 1
    while path.exists():
        path = directory / f"{stem}_{suffix:02d}.json"
        suffix += 1
    return path


def run_wake_selection(
    *,
    agent_dir: Path,
    registry_path: Path,
    venues_root: Path,
    explicit_candidates: list[str] | None = None,
    use_current_snapshots: bool = False,
    selector: WakeSelectorCommand | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = now or datetime.now(_JST)
    agent_dir = agent_dir.resolve()
    policy = _load_policy(agent_dir)
    state = _load_state(agent_dir)
    registry_schema: str | None = None
    registry_fingerprint: str | None = None
    validation_status = "accepted"
    validation_error: str | None = None
    omissions: list[dict[str, str]] = []
    raw_candidates: list[tuple[str, str]] = []
    try:
        venues, registry_fingerprint = _load_registry(registry_path)
        registry_schema = _REGISTRY_SCHEMA
        raw_candidates, omissions = _construct_candidates(
            venues=venues,
            venues_root=venues_root,
            explicit_candidates=explicit_candidates,
            use_current_snapshots=use_current_snapshots,
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        validation_status = "rejected"
        validation_error = " ".join(str(exc).split())[:360]

    candidates: list[dict[str, Any]] = []
    for venue_id, snapshot_id in raw_candidates:
        previous_id = _latest_snapshot_id(agent_dir, venue_id=venue_id)
        comparison_available = previous_id is not None
        candidates.append(
            {
                "venue_id": venue_id,
                "previous_snapshot_id": previous_id,
                "candidate_snapshot_id": snapshot_id,
                "comparison_available": comparison_available,
                "comparison_scope": (
                    "same_venue_history" if comparison_available else "same_venue_no_history"
                ),
                "changed": bool(comparison_available and previous_id != snapshot_id),
                "content_was_not_read": True,
            }
        )

    rest_started = state.get("rest_started_at")
    rest_started_text = str(rest_started) if rest_started else None
    elapsed_hours = _elapsed_rest_hours(rest_started_text, checked_at)
    fatigue = recovered_fatigue(
        float(state.get("fatigue", 0.0) or 0.0),
        rest_started_at=rest_started_text,
        now=checked_at,
    )
    blockers: list[str] = []
    if state.get("status") != "resting":
        blockers.append("visitor is not resting")
    if elapsed_hours < policy.minimum_rest_hours:
        blockers.append("minimum rest time has not elapsed")
    if fatigue > policy.maximum_fatigue_to_consider:
        blockers.append("fatigue remains above the wake threshold")
    eligible = not blockers

    selector_status = "not_invoked"
    selector_error: str | None = None
    if validation_status == "rejected":
        decision = _rejected_decision(f"candidate validation failed: {validation_error}")
        source = "deterministic_gate"
    elif not eligible:
        decision = WakeSelectionDecision(
            "remain_asleep", None, "; ".join(blockers), "deterministic body gate",
            "rest_preferred",
        )
        source = "deterministic_gate"
    elif not candidates:
        decision = WakeSelectionDecision(
            "remain_asleep", None, "No validated candidates were available.",
            "no candidate to select", "comparison_unavailable",
        )
        source = "deterministic_default"
    elif selector is None:
        decision = WakeSelectionDecision(
            "remain_asleep", None, "No command selector was invoked.",
            "deterministic mode never selects a Venue", "rest_preferred",
        )
        source = "deterministic_default"
    else:
        impulses = [
            " ".join(item.split())[:_MAX_IMPULSE_CHARACTERS]
            for item in state.get("unresolved_impulses", [])
            if isinstance(item, str) and item.strip()
        ][:_MAX_IMPULSES]
        payload = {
            "agent_id": state.get("id") or agent_dir.name,
            "unresolved_impulses": impulses,
            "rest": {
                "elapsed_hours": round(elapsed_hours, 4),
                "recovered_fatigue": round(fatigue, 4),
                "minimum_rest_hours": policy.minimum_rest_hours,
                "maximum_fatigue_to_consider": policy.maximum_fatigue_to_consider,
            },
            "candidates": candidates,
            "output_contract": {
                "decisions": ["remain_asleep", "select_venue"],
                "reason_codes": sorted(_REASON_CODES),
                "selection_must_be_exact_candidate_id": True,
                "selection_does_not_wake_or_start_a_visit": True,
            },
        }
        decision = selector.decide(
            payload, candidate_venue_ids={candidate["venue_id"] for candidate in candidates}
        )
        selector_status = decision.status
        selector_error = decision.error
        source = "command_selector"

    record_path = _next_record_path(agent_dir / "wake_selections", checked_at)
    record: dict[str, Any] = {
        "schema_version": _RECORD_SCHEMA,
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
        "registry": {
            "schema_version": registry_schema,
            "sha256": registry_fingerprint,
        },
        "candidate_validation": {
            "status": validation_status,
            "error": validation_error,
        },
        "candidates": candidates,
        "current_snapshot_omissions": omissions,
        "selector": {
            "status": selector_status,
            "model": selector.label if selector else None,
            "protocol": selector.protocol if selector else "deterministic-wake-selector-v0",
            "error": selector_error,
        },
        "decision": decision.decision,
        "selected_venue_id": decision.selected_venue_id,
        "observation": decision.observation,
        "reason": decision.reason,
        "reason_code": decision.reason_code,
        "state_status_after": state.get("status"),
        "current_location_after": state.get("current_location"),
        "content_was_not_read": True,
        "wake_was_not_run": True,
        "request_was_not_created": True,
        "visit_was_not_run": True,
        "selection_file": str(record_path),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-select-wake-venue")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--venues-root", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--candidate", action="append", default=[])
    modes.add_argument("--use-current-snapshots", action="store_true")
    parser.add_argument("--selector", choices=["deterministic", "command"], default="deterministic")
    parser.add_argument("--selector-command")
    parser.add_argument("--selector-label")
    parser.add_argument("--selector-timeout", type=float, default=45.0)
    args = parser.parse_args()
    selector: WakeSelectorCommand | None = None
    if args.selector == "command":
        if not args.selector_command:
            parser.error("--selector-command is required for command selector")
        selector = WakeSelectorCommand(
            shlex.split(args.selector_command),
            label=args.selector_label,
            timeout_seconds=args.selector_timeout,
        )
    result = run_wake_selection(
        agent_dir=args.agent,
        registry_path=args.registry,
        venues_root=args.venues_root,
        explicit_candidates=args.candidate,
        use_current_snapshots=args.use_current_snapshots,
        selector=selector,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
