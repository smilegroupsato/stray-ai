from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.visit_handoff import VisitHandoffError, prepare_visit_request

_JST = ZoneInfo("Asia/Tokyo")
_NOW = datetime(2026, 7, 22, 12, 0, tzinfo=_JST)


def _fixture(root: Path) -> tuple[Path, Path, Path]:
    agent = root / "agent"
    wake_dir = agent / "wake_checks"
    wake_dir.mkdir(parents=True)
    (agent / "profile.yml").write_text(
        """
id: test-stray
movement:
  max_places_per_visit: 3
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        '{"status":"resting","visit_count":4,"current_location":null}\n',
        encoding="utf-8",
    )
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")

    wake = wake_dir / "2026-07-22_110000.json"
    wake.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "checked_at": "2026-07-22T11:00:00+09:00",
                "eligible": True,
                "venue": {
                    "previous_snapshot_id": "snap-a",
                    "candidate_snapshot_id": "snap-b",
                    "changed": True,
                    "content_was_not_read": True,
                },
                "brain": {
                    "status": "accepted",
                    "model": "test-wake-model",
                    "protocol": "stray-wake-v1",
                    "error": None,
                },
                "decision": "request_visit",
                "observation": "The opaque identity changed.",
                "reason": "A later bounded encounter may matter.",
                "impulses_added": ["Notice only the difference."],
                "state_status_after": "resting",
                "current_location_after": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = root / "snap-b"
    snapshot.mkdir()
    (snapshot / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (snapshot / "NEXT.md").write_text("# Next\n", encoding="utf-8")
    return agent, wake, snapshot


def _protected(agent: Path, wake: Path) -> dict[Path, bytes]:
    files = [agent / "profile.yml", agent / "state.json", agent / "memory.md", wake]
    return {path: path.read_bytes() for path in files}


def test_prepare_visit_request_is_pending_idempotent_and_non_executing(tmp_path: Path) -> None:
    agent, wake, snapshot = _fixture(tmp_path)
    before = _protected(agent, wake)

    first = prepare_visit_request(
        agent_dir=agent,
        wake_file=wake,
        venue_id="test-venue",
        snapshot_root=snapshot,
        entrance=Path("README.md"),
        arrival_path=[Path("NEXT.md")],
        now=_NOW,
    )
    second = prepare_visit_request(
        agent_dir=agent,
        wake_file=wake,
        venue_id="test-venue",
        snapshot_root=snapshot,
        entrance=Path("README.md"),
        arrival_path=[Path("NEXT.md")],
        now=_NOW,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["request_file"] == second["request_file"]
    assert len(list((agent / "visit_requests").glob("*.json"))) == 1

    request = json.loads(Path(first["request_file"]).read_text(encoding="utf-8"))
    assert request["schema"] == "stray-visit-request-v1"
    assert request["status"] == "pending_human_approval"
    assert request["source_wake"] == "wake_checks/2026-07-22_110000.json"
    assert request["venue"]["snapshot_id"] == "snap-b"
    assert request["venue"]["entrance"] == "README.md"
    assert request["venue"]["arrival_path"] == ["NEXT.md"]
    assert request["constraints"] == {
        "max_places": 3,
        "venue_content_read": False,
        "visit_started": False,
        "human_approval_required": True,
        "automatic_execution_allowed": False,
    }
    assert request["approval"]["approved_at"] is None
    assert request["execution"]["started_at"] is None
    assert not (agent / "visits").exists()
    assert _protected(agent, wake) == before


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("eligible", False, "not eligible"),
        ("decision", "remain_asleep", "does not request"),
        ("state_status_after", "visiting", "not resting"),
        ("current_location_after", "/somewhere", "current location"),
    ],
)
def test_invalid_wake_records_fail_closed_without_request(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    agent, wake, snapshot = _fixture(tmp_path)
    record = json.loads(wake.read_text(encoding="utf-8"))
    record[field] = value
    wake.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(VisitHandoffError, match=message):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=snapshot,
            entrance=Path("README.md"),
        )
    assert not (agent / "visit_requests").exists()


def test_rejected_wake_and_untrusted_target_fail_closed(tmp_path: Path) -> None:
    agent, wake, snapshot = _fixture(tmp_path)
    record = json.loads(wake.read_text(encoding="utf-8"))
    record["brain"]["status"] = "rejected"
    wake.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(VisitHandoffError, match="not accepted"):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=snapshot,
            entrance=Path("README.md"),
        )

    record["brain"]["status"] = "accepted"
    wake.write_text(json.dumps(record), encoding="utf-8")
    wrong_snapshot = tmp_path / "snap-c"
    wrong_snapshot.mkdir()
    (wrong_snapshot / "README.md").write_text("# Wrong\n", encoding="utf-8")

    with pytest.raises(VisitHandoffError, match="does not match"):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=wrong_snapshot,
            entrance=Path("README.md"),
        )
    with pytest.raises(VisitHandoffError, match="must be relative"):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=snapshot,
            entrance=(snapshot / "README.md").resolve(),
        )
    assert not (agent / "visit_requests").exists()


def test_route_is_bounded_by_profile_without_reading_pages(tmp_path: Path) -> None:
    agent, wake, snapshot = _fixture(tmp_path)
    (snapshot / "THIRD.md").write_text("# Third\n", encoding="utf-8")
    (snapshot / "FOURTH.md").write_text("# Fourth\n", encoding="utf-8")

    with pytest.raises(VisitHandoffError, match="exceeds max_places"):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=snapshot,
            entrance=Path("README.md"),
            arrival_path=[Path("NEXT.md"), Path("THIRD.md"), Path("FOURTH.md")],
        )
    with pytest.raises(VisitHandoffError, match="duplicate"):
        prepare_visit_request(
            agent_dir=agent,
            wake_file=wake,
            venue_id="test-venue",
            snapshot_root=snapshot,
            entrance=Path("README.md"),
            arrival_path=[Path("NEXT.md"), Path("NEXT.md")],
        )
    assert not (agent / "visit_requests").exists()
