from __future__ import annotations

import json
import sys
from pathlib import Path

from stray_ai.brain import CommandBrain, normalize_decision
from stray_ai.visitor import run_visit


def _agent(root: Path, *, max_trace: int = 100) -> Path:
    agent = root / "agent"
    agent.mkdir()
    (agent / "profile.yml").write_text(
        f"""
id: test-stray
name: unnamed
attention:
  drawn_to: [unfinished traces]
  tends_to_avoid: [advertisements]
movement:
  max_places_per_visit: 2
  may_leave_silently: true
memory:
  max_new_memories_per_visit: 2
trace:
  max_characters: {max_trace}
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


def _venue(root: Path) -> Path:
    venue = root / "venue"
    venue.mkdir()
    (venue / "README.md").write_text(
        "# Entrance\n\nA narrow path.\n\n[Continue](next.md)\n", encoding="utf-8"
    )
    (venue / "next.md").write_text(
        "# Unfinished Room\n\nA sentence stops before it explains itself.\n",
        encoding="utf-8",
    )
    return venue


def test_command_brain_can_follow_and_carry_trace(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        """
import json, sys
request = json.load(sys.stdin)
if request["page"]["title"] == "Entrance":
    result = {
        "action": "follow_link",
        "link_index": 0,
        "observation": "The unfinished path is more specific than the entrance.",
        "memories": ["The entrance offered one narrow continuation."],
        "trace": None,
    }
else:
    result = {
        "action": "carry_trace",
        "link_index": None,
        "observation": "The sentence preserves its edge by stopping.",
        "memories": ["An unfinished sentence can keep a place open."],
        "trace": "The room did not ask to be completed; its stopping point was the invitation.",
    }
print(json.dumps(result))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    agent = _agent(tmp_path)
    venue = _venue(tmp_path)
    brain = CommandBrain([sys.executable, str(adapter)], label="test-model", timeout_seconds=5)

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        brain=brain,
    )

    assert result["backend"] == "command"
    assert result["brain_model"] == "test-model"
    assert result["exit_reason"] == "trace_carried_home"
    assert result["steps"][0]["action"] == "follow_link"
    assert result["steps"][0]["brain"]["status"] == "accepted"
    assert result["steps"][1]["action"] == "leave_trace"
    assert Path(result["visit_file"]).exists()
    trace = Path(result["trace_file"]).read_text(encoding="utf-8")
    assert "stopping point was the invitation" in trace
    memory = (agent / "memory.md").read_text(encoding="utf-8")
    assert "unfinished sentence can keep a place open" in memory


def test_invalid_link_fails_closed_and_preserves_visit(tmp_path: Path) -> None:
    adapter = tmp_path / "bad-adapter.py"
    adapter.write_text(
        'import json,sys; json.load(sys.stdin); print(json.dumps({"action":"follow_link","link_index":99,"observation":"escape","memories":[],"trace":None}))\n',
        encoding="utf-8",
    )
    agent = _agent(tmp_path)
    venue = _venue(tmp_path)
    brain = CommandBrain([sys.executable, str(adapter)], label="bad-model", timeout_seconds=5)

    result = run_visit(
        agent_dir=agent,
        local_root=venue,
        entrance=venue / "README.md",
        outbox=tmp_path / "outbox",
        brain=brain,
    )

    assert result["exit_reason"] == "brain_failed_safe_exit"
    assert result["trace_file"] is None
    assert result["steps"][0]["action"] == "leave"
    assert result["steps"][0]["brain"]["status"] == "rejected"
    assert "outside the bounded candidates" in result["steps"][0]["brain"]["error"]
    assert Path(result["visit_file"]).exists()


def test_decision_limits_trace_and_memories() -> None:
    decision = normalize_decision(
        {
            "action": "carry_trace",
            "link_index": None,
            "observation": "noticed",
            "memories": ["a" * 400, "second", "third"],
            "trace": "t" * 400,
        },
        link_count=0,
        can_follow=False,
        max_memories=2,
        max_trace_characters=80,
    )

    assert decision.status == "accepted"
    assert len(decision.trace or "") == 80
    assert len(decision.memories or []) == 2
    assert len((decision.memories or [""])[0]) == 240
