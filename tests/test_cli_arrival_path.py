from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_resolves_relative_arrival_path_inside_venue(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    venue = tmp_path / "venue"
    outbox = tmp_path / "outbox"
    agent.mkdir()
    venue.mkdir()

    (agent / "profile.yml").write_text(
        """
id: cli-stray
name: unnamed
attention:
  drawn_to: [trace]
  tends_to_avoid: []
movement:
  max_places_per_visit: 3
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
    (venue / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (venue / "REPOSITORY_CONTEXT.md").write_text("# Map\n", encoding="utf-8")
    (venue / "AGENTS.md").write_text("# Reception\n\nA trace remains.\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "stray_ai.cli",
            "--agent",
            str(agent),
            "--local-root",
            str(venue),
            "--entrance",
            str(venue / "README.md"),
            "--arrival-path",
            "REPOSITORY_CONTEXT.md",
            "AGENTS.md",
            "--outbox",
            str(outbox),
            "--seed",
            "7",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(completed.stdout)

    assert [step["title"] for step in result["steps"]] == ["Entrance", "Map", "Reception"]
