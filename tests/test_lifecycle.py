from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.brain import CommandBrain
from stray_ai.lifecycle import migrate_agent, recovered_fatigue
from stray_ai.visitor import run_visit

_JST = ZoneInfo("Asia/Tokyo")


def _write_profile(agent: Path) -> None:
    (agent / "profile.yml").write_text(
        """
id: test-stray
name: unnamed
attention:
  drawn_to: [trace]
  tends_to_avoid: []
movement:
  max_places_per_visit: 2
  may_leave_silently: true
memory:
  max_new_memories_per_visit: 2
trace:
  max_characters: 100
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_legacy_agent_migration_is_idempotent(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    visits = agent / "visits"
    visits.mkdir(parents=True)
    _write_profile(agent)
    timestamped = "## 2026-07-20T12:20:31+09:00\n- A real memory survived.\n"
    (agent / "memory.md").write_text(
        "# Memory\n\n"
        "No place has yet become a memory.\n\n"
        "The visitor has not completed its first visit.\n\n"
        + timestamped,
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "awake",
                "visit_count": 2,
                "current_location": "/venue/old.md",
                "last_visit": "2026-07-20T12:20:31+09:00",
                "fatigue": 0.92,
                "unresolved_impulses": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    records = [
        {
            "ended_at": "2026-07-20T11:14:36+09:00",
            "backend": "mock",
            "brain_model": None,
            "exit_reason": "trace_carried_home",
            "steps": [
                {
                    "location": "/venue/becoming.md",
                    "brain": {"status": "accepted"},
                }
            ],
        },
        {
            "ended_at": "2026-07-20T12:20:31+09:00",
            "backend": "command",
            "brain_model": "qwen3.5:9b",
            "exit_reason": "left_silently",
            "steps": [
                {
                    "location": "/venue/AGENTS.md",
                    "brain": {"status": "accepted"},
                }
            ],
        },
    ]
    for index, record in enumerate(records):
        (visits / f"{index}.json").write_text(json.dumps(record), encoding="utf-8")

    first = migrate_agent(agent)
    memory_after_first = (agent / "memory.md").read_bytes()
    state_after_first = (agent / "state.json").read_bytes()
    second = migrate_agent(agent)

    assert first == {
        "memory_changed": True,
        "memory_records_changed": False,
        "state_changed": True,
    }
    assert second == {
        "memory_changed": False,
        "memory_records_changed": False,
        "state_changed": False,
    }
    assert (agent / "memory.md").read_bytes() == memory_after_first
    assert (agent / "state.json").read_bytes() == state_after_first
    memory = memory_after_first.decode()
    assert timestamped in memory
    assert "has not completed its first visit" not in memory
    state = json.loads(state_after_first)
    assert state["status"] == "resting"
    assert state["current_location"] is None
    assert state["last_location"] == "/venue/AGENTS.md"
    assert state["visit_count"] == 2
    assert state["llm_visit_count"] == 1
    assert state["accepted_brain_visit_count"] == 1
    assert state["safe_exit_count"] == 0


def test_fatigue_recovers_deterministically() -> None:
    started = datetime(2026, 7, 20, 10, 0, tzinfo=_JST)
    later = started + timedelta(hours=5)
    assert recovered_fatigue(
        0.92,
        rest_started_at=started.isoformat(),
        now=later,
    ) == pytest.approx(0.72)
    assert recovered_fatigue(
        0.1,
        rest_started_at=started.isoformat(),
        now=started + timedelta(hours=10),
    ) == 0.0


def test_future_brain_receives_recovered_state_without_stale_bootstrap(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_profile(agent)
    rest_started = datetime.now(_JST) - timedelta(hours=5)
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "visit_count": 1,
                "current_location": None,
                "last_visit": rest_started.isoformat(),
                "rest_started_at": rest_started.isoformat(),
                "fatigue": 0.8,
                "unresolved_impulses": [],
            }
        ),
        encoding="utf-8",
    )
    (agent / "memory.md").write_text(
        "# Memory\n\n"
        "No place has yet become a memory.\n\n"
        "The visitor has not completed its first visit.\n",
        encoding="utf-8",
    )
    venue = tmp_path / "venue"
    venue.mkdir()
    (venue / "README.md").write_text("# Entrance\n", encoding="utf-8")
    captured = tmp_path / "captured.json"
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        """
import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path(sys.argv[1]).write_text(json.dumps(request))
print(json.dumps({
  "action": "leave_silently",
  "link_index": None,
  "observation": "Rest was noticed.",
  "memories": [],
  "trace": None
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    brain = CommandBrain(
        [sys.executable, str(adapter), str(captured)],
        label="test-model",
        timeout_seconds=5,
    )

    run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        brain=brain,
    )

    request = json.loads(captured.read_text(encoding="utf-8"))
    assert request["state"]["status"] == "visiting"
    assert request["state"]["fatigue"] < 0.8
    assert "has not completed its first visit" not in request["visitor"]["memory_excerpt"]
    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "resting"
    assert state["current_location"] is None
    assert state["last_location"] == str((venue / "README.md").resolve())


def test_fail_closed_visit_returns_home(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_profile(agent)
    (agent / "state.json").write_text("{}\n", encoding="utf-8")
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")
    venue = tmp_path / "venue"
    venue.mkdir()
    (venue / "README.md").write_text("# Entrance\n\n[Next](next.md)\n", encoding="utf-8")
    (venue / "next.md").write_text("# Next\n", encoding="utf-8")
    adapter = tmp_path / "bad.py"
    adapter.write_text(
        'import json,sys; json.load(sys.stdin); print(json.dumps({"action":"follow_link","link_index":99,"observation":"escape"}))\n',
        encoding="utf-8",
    )
    brain = CommandBrain([sys.executable, str(adapter)], label="bad-model", timeout_seconds=5)

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        brain=brain,
    )

    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert result["exit_reason"] == "brain_failed_safe_exit"
    assert state["status"] == "resting"
    assert state["current_location"] is None
    assert state["safe_exit_count"] == 1
    assert state["llm_visit_count"] == 1
    assert state["accepted_brain_visit_count"] == 0
