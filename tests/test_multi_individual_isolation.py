from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.report_collection import generate_report_collection
from stray_ai.visit_execution import VisitExecutionError, approve_visit_request
from stray_ai.visit_handoff import VisitHandoffError, prepare_visit_request
from stray_ai.wake import WakeCommandBrain, run_wake_check
from stray_ai.wake_selection import run_wake_selection

_JST = ZoneInfo("Asia/Tokyo")
_NOW = datetime(2026, 7, 24, 12, 0, tzinfo=_JST)


def _write_agent(
    agents_dir: Path,
    *,
    agent_id: str,
    display_name: str,
    memory_marker: str,
    impulse: str,
    previous_snapshot: str,
    page_prefix: str,
) -> Path:
    agent_dir = agents_dir / agent_id
    visits_dir = agent_dir / "visits"
    visits_dir.mkdir(parents=True)
    (agent_dir / "profile.yml").write_text(
        (
            f"id: {agent_id}\n"
            f"name: {display_name}\n"
            "kind: visitor\n"
            "wake:\n"
            "  minimum_rest_hours: 0\n"
            "  maximum_fatigue_to_consider: 0.5\n"
            "movement:\n"
            "  max_places_per_visit: 3\n"
        ),
        encoding="utf-8",
    )
    (agent_dir / "state.json").write_text(
        json.dumps(
            {
                "id": agent_id,
                "status": "resting",
                "current_location": None,
                "rest_started_at": "2026-07-23T00:00:00+09:00",
                "fatigue": 0.1,
                "visit_count": 1,
                "unresolved_impulses": [impulse],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (agent_dir / "memory.md").write_text(
        f"# Memory\n\n{memory_marker}\n",
        encoding="utf-8",
    )
    visit = {
        "agent_id": agent_id,
        "started_at": "2026-07-23T10:00:00+09:00",
        "ended_at": "2026-07-23T10:01:00+09:00",
        "entrance": f"/synthetic/venue-a/{previous_snapshot}/README.md",
        "backend": "mock",
        "steps": [
            {
                "step": 1,
                "location": f"/synthetic/venue-a/{previous_snapshot}/README.md",
                "title": f"{page_prefix} Entrance",
                "action": "leave",
            }
        ],
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
    }
    (visits_dir / f"{agent_id}-visit.json").write_text(
        json.dumps(visit, indent=2) + "\n",
        encoding="utf-8",
    )
    return agent_dir


def _protected(agent_dir: Path) -> dict[str, bytes]:
    return {
        name: (agent_dir / name).read_bytes()
        for name in ("profile.yml", "state.json", "memory.md")
    }


def test_two_individuals_remain_isolated_across_selection_wake_request_and_report(
    tmp_path: Path,
) -> None:
    agents_dir = tmp_path / "agents"
    first = _write_agent(
        agents_dir,
        agent_id="stray-001",
        display_name="first visitor",
        memory_marker="MEMORY-ONLY-001",
        impulse="Follow the open path.",
        previous_snapshot="snap-old-001",
        page_prefix="Alpha",
    )
    second = _write_agent(
        agents_dir,
        agent_id="stray-002",
        display_name="document maniac",
        memory_marker="MEMORY-ONLY-002",
        impulse="Return to the damp shelf gap.",
        previous_snapshot="snap-old-002",
        page_prefix="Beta",
    )
    protected_before = {
        "stray-001": _protected(first),
        "stray-002": _protected(second),
    }

    venues_root = tmp_path / "venues"
    snapshots = {
        "stray-001": venues_root / "venue-a" / "snap-next-001",
        "stray-002": venues_root / "venue-a" / "snap-next-002",
    }
    for agent_id, snapshot in snapshots.items():
        snapshot.mkdir(parents=True)
        (snapshot / "README.md").write_text(
            f"# Synthetic entrance for {agent_id}\n",
            encoding="utf-8",
        )
    registry = tmp_path / "venues.yml"
    registry.write_text(
        (
            "schema_version: 0.1\n"
            "venues:\n"
            "  - venue_id: venue-a\n"
            "    display_name: Synthetic Venue\n"
            "    selection_enabled: true\n"
        ),
        encoding="utf-8",
    )

    selections: dict[str, dict[str, object]] = {}
    for index, (agent_id, agent_dir) in enumerate(
        (("stray-001", first), ("stray-002", second))
    ):
        selections[agent_id] = run_wake_selection(
            agent_dir=agent_dir,
            registry_path=registry,
            venues_root=venues_root,
            explicit_candidates=[f"venue-a=snap-next-00{index + 1}"],
            now=_NOW,
        )

    assert selections["stray-001"]["agent_id"] == "stray-001"
    assert selections["stray-002"]["agent_id"] == "stray-002"
    assert Path(str(selections["stray-001"]["selection_file"])).parent == (
        first / "wake_selections"
    )
    assert Path(str(selections["stray-002"]["selection_file"])).parent == (
        second / "wake_selections"
    )

    brain_script = tmp_path / "wake_brain.py"
    brain_script.write_text(
        (
            "import json, sys\n"
            "json.load(sys.stdin)\n"
            "print(json.dumps({\n"
            "  'decision': 'request_visit',\n"
            "  'observation': 'A bounded synthetic difference was observed.',\n"
            "  'reason': 'Isolation validation only.',\n"
            "  'impulses': []\n"
            "}))\n"
        ),
        encoding="utf-8",
    )
    brain = WakeCommandBrain(
        [sys.executable, str(brain_script)],
        label="synthetic-isolation-brain",
    )
    wake_records: dict[str, Path] = {}
    for agent_id, agent_dir in (("stray-001", first), ("stray-002", second)):
        result = run_wake_check(
            agent_dir=agent_dir,
            candidate_venue_id="venue-a",
            candidate_snapshot_id=snapshots[agent_id].name,
            brain=brain,
            now=_NOW,
        )
        assert result["agent_id"] == agent_id
        assert result["decision"] == "request_visit"
        wake_records[agent_id] = Path(result["wake_file"])
        assert wake_records[agent_id].parent == agent_dir / "wake_checks"

    with pytest.raises(VisitHandoffError, match="inside the agent wake_checks"):
        prepare_visit_request(
            agent_dir=first,
            wake_file=wake_records["stray-002"],
            venue_id="venue-a",
            snapshot_root=snapshots["stray-002"],
            entrance=Path("README.md"),
            now=_NOW,
        )
    assert not (first / "visit_requests").exists()

    request_paths: dict[str, Path] = {}
    for agent_id, agent_dir in (("stray-001", first), ("stray-002", second)):
        prepared = prepare_visit_request(
            agent_dir=agent_dir,
            wake_file=wake_records[agent_id],
            venue_id="venue-a",
            snapshot_root=snapshots[agent_id],
            entrance=Path("README.md"),
            now=_NOW,
        )
        request_paths[agent_id] = Path(prepared["request_file"])
        assert prepared["request"]["agent_id"] == agent_id
        assert request_paths[agent_id].parent == agent_dir / "visit_requests"

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    foreign_request = second / "visit_requests" / request_paths["stray-001"].name
    foreign_request.write_bytes(request_paths["stray-001"].read_bytes())
    with pytest.raises(VisitExecutionError, match="different agent"):
        approve_visit_request(
            agent_dir=second,
            request_file=foreign_request,
            confirm_request_id=foreign_request.stem,
            approved_by="Synthetic validator",
            backend="mock",
            outbox=outbox,
            now=_NOW,
        )

    reports = tmp_path / "reports"
    result = generate_report_collection(
        agents_dir,
        reports,
        primary_agent_id="stray-001",
    )
    assert result["primary_agent_id"] == "stray-001"
    assert [item["agent_id"] for item in result["individuals"]] == [
        "stray-001",
        "stray-002",
    ]

    first_report = reports / "individuals" / "stray-001"
    second_report = reports / "individuals" / "stray-002"
    first_map = (first_report / "map.html").read_text(encoding="utf-8")
    second_map = (second_report / "map.html").read_text(encoding="utf-8")
    assert "Alpha Entrance" in first_map
    assert "Beta Entrance" not in first_map
    assert "Beta Entrance" in second_map
    assert "Alpha Entrance" not in second_map
    assert (reports / "visits.html").read_bytes() == (
        first_report / "index.html"
    ).read_bytes()
    assert (reports / "map.html").read_bytes() == (
        first_report / "map.html"
    ).read_bytes()

    generated_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in reports.rglob("*.html")
    )
    assert "MEMORY-ONLY-001" not in generated_text
    assert "MEMORY-ONLY-002" not in generated_text
    assert not (first / "visit_requests" / "claims").exists()
    assert not (second / "visit_requests" / "claims").exists()
    assert len(list((first / "visits").glob("*.json"))) == 1
    assert len(list((second / "visits").glob("*.json"))) == 1
    assert _protected(first) == protected_before["stray-001"]
    assert _protected(second) == protected_before["stray-002"]
