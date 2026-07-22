from __future__ import annotations

import json
import sys
from pathlib import Path

from stray_ai.brain import CommandBrain
from stray_ai.lifecycle import migrate_agent
from stray_ai.memory_records import load_memory_records
from stray_ai.visitor import run_visit


def _write_profile(agent: Path) -> None:
    (agent / "profile.yml").write_text(
        """
id: test-stray
name: unnamed
attention:
  drawn_to: [memory]
  tends_to_avoid: []
movement:
  max_places_per_visit: 1
  may_leave_silently: true
memory:
  max_new_memories_per_visit: 2
trace:
  max_characters: 100
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _new_agent(root: Path) -> Path:
    agent = root / "agent"
    agent.mkdir()
    _write_profile(agent)
    (agent / "state.json").write_text("{}\n", encoding="utf-8")
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")
    return agent


def test_new_memory_keeps_system_time_and_visit_source_separate(tmp_path: Path) -> None:
    agent = _new_agent(tmp_path)
    venue = tmp_path / "venue"
    venue.mkdir()
    (venue / "README.md").write_text("# Entrance\n\nA remembered room.\n", encoding="utf-8")

    authored = (
        "2026-07-20T14:35:12+09:00 - The model wrote this time inside the memory text."
    )
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        """
import json, sys
json.load(sys.stdin)
print(json.dumps({
  "action": "leave_silently",
  "link_index": None,
  "observation": "A memory was selected.",
  "memories": [sys.argv[1]],
  "trace": None
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    brain = CommandBrain(
        [sys.executable, str(adapter), authored],
        label="test-model",
        timeout_seconds=5,
    )

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        brain=brain,
    )

    records = load_memory_records(agent / "memory_records.jsonl")
    assert len(records) == 1
    record = records[0]
    assert result["memories_added"] == [authored]
    assert record["text"] == authored
    assert record["recorded_at"] == result["ended_at"]
    assert record["source_visit"] == f"visits/{Path(result['visit_file']).name}"
    assert record["source_step"] == 1
    assert record["model_authored_time"] is None
    assert authored in (agent / "memory.md").read_text(encoding="utf-8")


def test_migration_backfills_without_changing_existing_visit_or_memory(tmp_path: Path) -> None:
    agent = _new_agent(tmp_path)
    visits = agent / "visits"
    visits.mkdir()
    authored = "2026-07-20T14:38:45+09:00 - A model-authored time remains plain text."
    visit_path = visits / "2026-07-21_130524.json"
    visit_path.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "started_at": "2026-07-21T13:05:24+09:00",
                "ended_at": "2026-07-21T13:06:40+09:00",
                "backend": "command",
                "brain_model": "test-model",
                "exit_reason": "left_silently",
                "steps": [{"location": "/venue/AFTERHOURS.md"}],
                "memories_added": [authored],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    memory_before = (agent / "memory.md").read_bytes()
    visit_before = visit_path.read_bytes()

    first = migrate_agent(agent)
    records_after_first = (agent / "memory_records.jsonl").read_bytes()
    second = migrate_agent(agent)

    assert first["memory_records_changed"] is True
    assert second["memory_records_changed"] is False
    assert (agent / "memory.md").read_bytes() == memory_before
    assert visit_path.read_bytes() == visit_before
    assert (agent / "memory_records.jsonl").read_bytes() == records_after_first

    records = load_memory_records(agent / "memory_records.jsonl")
    assert len(records) == 1
    assert records[0]["text"] == authored
    assert records[0]["recorded_at"] == "2026-07-21T13:06:40+09:00"
    assert records[0]["source_visit"] == "visits/2026-07-21_130524.json"
    assert records[0]["source_step"] is None
    assert records[0]["model_authored_time"] is None
