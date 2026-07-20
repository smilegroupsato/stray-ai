import json
from pathlib import Path

import pytest

from stray_ai.visitor import StrayError, run_visit


def _agent(root: Path, *, max_places: int = 2) -> Path:
    agent = root / "agent"
    agent.mkdir()
    (agent / "profile.yml").write_text(
        f"""
id: test-stray
name: unnamed
attention:
  drawn_to: [trace]
  tends_to_avoid: []
movement:
  max_places_per_visit: {max_places}
  may_leave_silently: false
memory:
  max_new_memories_per_visit: 2
trace:
  max_characters: 100
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        '{"status":"unborn","visit_count":0,"current_location":null,"last_visit":null,"fatigue":0.0,"unresolved_impulses":[]}\n',
        encoding="utf-8",
    )
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")
    return agent


def test_first_visit_persists_identity(tmp_path: Path) -> None:
    venue = tmp_path / "venue"
    venue.mkdir()
    (venue / "README.md").write_text("# Entrance\n\n[Next](next.md)\n", encoding="utf-8")
    (venue / "next.md").write_text("# Trace\n\nA trace remains.\n", encoding="utf-8")
    agent = _agent(tmp_path)

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        seed=1,
    )

    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    record = json.loads(Path(result["visit_file"]).read_text(encoding="utf-8"))
    assert state["status"] == "resting"
    assert state["visit_count"] == 1
    assert state["current_location"] is None
    assert state["last_location"] == str((venue / "next.md").resolve())
    assert state["last_exit_reason"] == "trace_carried_home"
    assert state["rest_started_at"] == state["last_visit"]
    assert Path(result["visit_file"]).exists()
    assert record["visit_file"] == result["visit_file"]
    assert Path(result["trace_file"]).exists()


def test_trusted_arrival_path_precedes_free_wandering(tmp_path: Path) -> None:
    venue = tmp_path / "venue"
    venue.mkdir()
    (venue / "README.md").write_text(
        "# Entrance\n\n[Tempting](random.md)\n", encoding="utf-8"
    )
    (venue / "random.md").write_text("# Random Trace\n", encoding="utf-8")
    (venue / "REPOSITORY_CONTEXT.md").write_text("# Map\n", encoding="utf-8")
    (venue / "AGENTS.md").write_text("# Reception\n\nA trace remains.\n", encoding="utf-8")
    agent = _agent(tmp_path, max_places=3)

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        arrival_path=[venue / "REPOSITORY_CONTEXT.md", venue / "AGENTS.md"],
        outbox=tmp_path / "outbox",
        seed=1,
    )

    assert [step["title"] for step in result["steps"]] == ["Entrance", "Map", "Reception"]
    assert result["steps"][0]["action"] == "follow_arrival_path"
    assert result["steps"][1]["action"] == "follow_arrival_path"
    assert result["arrival_path"] == [
        str((venue / "README.md").resolve()),
        str((venue / "REPOSITORY_CONTEXT.md").resolve()),
        str((venue / "AGENTS.md").resolve()),
    ]


def test_bounded_venue_blocks_escape(tmp_path: Path) -> None:
    venue = tmp_path / "venue"
    venue.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    agent = _agent(tmp_path)

    with pytest.raises(StrayError):
        run_visit(
            agent_dir=agent,
            local_root=venue,
            entrance=outside,
            outbox=tmp_path / "outbox",
            seed=1,
        )
