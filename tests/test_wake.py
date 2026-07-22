from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from stray_ai.wake import WakeCommandBrain, normalize_wake_decision, run_wake_check

_JST = ZoneInfo("Asia/Tokyo")
_BASE = datetime(2026, 7, 20, 12, 0, tzinfo=_JST)


def _write_visit(
    agent: Path,
    *,
    filename: str,
    venue_id: str,
    snapshot_id: str,
) -> Path:
    path = agent / "visits" / filename
    path.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "entrance": f"/venues/{venue_id}/{snapshot_id}/README.md",
                "backend": "command",
                "steps": [
                    {
                        "location": f"/venues/{venue_id}/{snapshot_id}/AGENTS.md"
                    }
                ],
                "exit_reason": "left_silently",
            }
        ),
        encoding="utf-8",
    )
    return path


def _agent(root: Path, *, fatigue: float = 0.9, rest_hours: float = 1.0) -> Path:
    agent = root / "agent"
    agent.mkdir()
    (agent / "profile.yml").write_text(
        """
id: test-stray
name: unnamed
wake:
  minimum_rest_hours: 12
  maximum_fatigue_to_consider: 0.5
  max_new_impulses_per_check: 1
""".strip()
        + "\n",
        encoding="utf-8",
    )
    rest_started = (_BASE - timedelta(hours=rest_hours)).isoformat()
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "visit_count": 4,
                "llm_visit_count": 2,
                "accepted_brain_visit_count": 1,
                "safe_exit_count": 1,
                "current_location": None,
                "last_location": "/venues/venue-a/snap-a/AGENTS.md",
                "last_visit": rest_started,
                "rest_started_at": rest_started,
                "last_exit_reason": "left_silently",
                "last_backend": "command",
                "last_model": "test-model",
                "fatigue": fatigue,
                "unresolved_impulses": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (agent / "memory.md").write_text(
        "# Memory\n\n## earlier\n- A quiet reception remained.\n",
        encoding="utf-8",
    )
    (agent / "visits").mkdir()
    _write_visit(
        agent,
        filename="2026-07-20_100000.json",
        venue_id="venue-a",
        snapshot_id="snap-a",
    )
    return agent


def _adapter(path: Path, body: str) -> WakeCommandBrain:
    script = path / "wake-adapter.py"
    script.write_text(body.strip() + "\n", encoding="utf-8")
    return WakeCommandBrain([sys.executable, str(script)], label="test-wake-model", timeout_seconds=5)


def test_recent_fatigued_visitor_remains_asleep_without_invoking_brain(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.9, rest_hours=1)
    marker = tmp_path / "invoked"
    brain = _adapter(
        tmp_path,
        f"""
from pathlib import Path
Path({str(marker)!r}).write_text("called")
print('{{"decision":"request_visit","observation":"x","reason":"x","impulses":[]}}')
""",
    )

    before_state = (agent / "state.json").read_text(encoding="utf-8")
    result = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-a",
        brain=brain,
        now=_BASE,
    )

    assert result["eligible"] is False
    assert result["decision"] == "remain_asleep"
    assert result["source"] == "deterministic_gate"
    assert result["brain"]["status"] == "not_invoked"
    assert not marker.exists()
    assert Path(result["wake_file"]).exists()
    assert (agent / "state.json").read_text(encoding="utf-8") == before_state


def test_eligible_deterministic_check_can_still_choose_sleep(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)

    result = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-a",
        now=_BASE,
    )

    assert result["eligible"] is True
    assert result["decision"] == "remain_asleep"
    assert result["source"] == "deterministic_default"
    assert result["venue"]["candidate_venue_id"] == "venue-a"
    assert result["venue"]["comparison_available"] is True
    assert result["venue"]["comparison_scope"] == "same_venue_history"
    assert result["venue"]["changed"] is False
    assert result["venue"]["content_was_not_read"] is True


def test_latest_snapshot_is_selected_only_from_same_venue(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)
    _write_visit(
        agent,
        filename="2026-07-20_110000.json",
        venue_id="venue-b",
        snapshot_id="snap-b",
    )

    unchanged = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-a",
        now=_BASE,
    )
    changed = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-c",
        now=_BASE + timedelta(seconds=1),
    )

    assert unchanged["venue"]["previous_snapshot_id"] == "snap-a"
    assert unchanged["venue"]["changed"] is False
    assert changed["venue"]["previous_snapshot_id"] == "snap-a"
    assert changed["venue"]["changed"] is True


def test_missing_venue_id_never_falls_back_to_cross_venue_history(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)

    result = run_wake_check(
        agent_dir=agent,
        candidate_snapshot_id="snap-b",
        now=_BASE,
    )

    assert result["venue"]["candidate_venue_id"] is None
    assert result["venue"]["previous_snapshot_id"] is None
    assert result["venue"]["comparison_available"] is False
    assert result["venue"]["comparison_scope"] == "unavailable_no_venue"
    assert result["venue"]["changed"] is False


def test_explicit_previous_snapshot_remains_supported(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)

    result = run_wake_check(
        agent_dir=agent,
        candidate_snapshot_id="snap-b",
        previous_snapshot_id="snap-a",
        now=_BASE,
    )

    assert result["venue"]["comparison_available"] is True
    assert result["venue"]["comparison_scope"] == "explicit_previous"
    assert result["venue"]["changed"] is True


def test_eligible_brain_can_request_visit_and_add_one_deduplicated_impulse(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)
    brain = _adapter(
        tmp_path,
        """
import json, sys
request = json.load(sys.stdin)
assert request["venue"]["candidate_venue_id"] == "venue-a"
assert request["venue"]["comparison_scope"] == "same_venue_history"
assert request["venue"]["content_was_not_read"] is True
assert "content" not in request["venue"]
print(json.dumps({
  "decision": "request_visit",
  "observation": "The opaque snapshot identity changed.",
  "reason": "A small difference may be worth encountering.",
  "impulses": ["Return only to notice the difference.", "ignored second impulse"]
}))
""",
    )

    visit_path = next((agent / "visits").glob("*.json"))
    visit_before = visit_path.read_bytes()
    result = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-b",
        brain=brain,
        now=_BASE,
    )
    second = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-b",
        previous_snapshot_id="snap-a",
        brain=brain,
        now=_BASE + timedelta(seconds=1),
    )

    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert result["eligible"] is True
    assert result["decision"] == "request_visit"
    assert result["brain"]["status"] == "accepted"
    assert result["venue"]["changed"] is True
    assert result["impulses_added"] == ["Return only to notice the difference."]
    assert second["impulses_added"] == []
    assert state["unresolved_impulses"] == ["Return only to notice the difference."]
    assert state["status"] == "resting"
    assert state["current_location"] is None
    assert state["visit_count"] == 4
    assert visit_path.read_bytes() == visit_before
    assert len(list((agent / "wake_checks").glob("*.json"))) == 2


def test_invalid_brain_output_fails_closed_to_sleep(tmp_path: Path) -> None:
    agent = _agent(tmp_path, fatigue=0.2, rest_hours=24)
    brain = _adapter(tmp_path, 'print("{\\"decision\\":\\"wake\\"}")')

    result = run_wake_check(
        agent_dir=agent,
        candidate_venue_id="venue-a",
        candidate_snapshot_id="snap-b",
        brain=brain,
        now=_BASE,
    )

    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert result["decision"] == "remain_asleep"
    assert result["brain"]["status"] == "rejected"
    assert "not allowed" in (result["brain"]["error"] or "")
    assert state["unresolved_impulses"] == []
    assert state["visit_count"] == 4


def test_sleep_decision_discards_impulses() -> None:
    decision = normalize_wake_decision(
        {
            "decision": "remain_asleep",
            "observation": "rest",
            "reason": "nothing specific",
            "impulses": ["should not persist"],
        }
    )

    assert decision.decision == "remain_asleep"
    assert decision.impulses == []
