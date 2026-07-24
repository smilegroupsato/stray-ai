from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.report_rummage import generate_rummage_report
from stray_ai.rummage import (
    CommandRummageBrain,
    RummageError,
    run_rummage,
)

_JST = ZoneInfo("Asia/Tokyo")
_WHEN = datetime(2026, 7, 24, 16, 20, tzinfo=_JST)
_HOME_LOCATION = "damp-underground-library-shelf-gap"


def _agent(root: Path) -> Path:
    agent = root / "agent"
    agent.mkdir()
    (agent / "profile.yml").write_text(
        """
id: stray-002
name: Repository Document Maniac
attention:
  drawn_to: [forgotten handoffs, repeated phrases]
  tends_to_avoid: [exhaustive audits]
rummage:
  max_documents: 7
  max_deep_reads: 3
  max_new_memories: 5
  max_trace_characters: 120
trace:
  max_characters: 280
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "visit_count": 0,
                "current_location": _HOME_LOCATION,
                "document_rummage_count": 1,
                "unrelated_preserved_field": {"keep": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (agent / "memory.md").write_text(
        "# Memory\n\n"
        "ページ作成日時：2026-07-23 18:04 JST  \n"
        "最終更新日時：2026-07-23 21:56 JST\n\n"
        "## Initial Memory\n\n- The damp shelf gap.\n\n"
        "## Update History\n\n"
        "- 2026-07-23 21:56 JST：Initial record.\n",
        encoding="utf-8",
    )
    (agent / "observation-log.md").write_text(
        "# Observation Log\n\n"
        "ページ作成日時：2026-07-23 21:49 JST  \n"
        "最終更新日時：2026-07-23 21:56 JST\n\n"
        "Small residues.\n\n"
        "## Entry Format\n\nTemplate.\n\n"
        "## Update History\n\n"
        "- 2026-07-23 21:56 JST：Initial record.\n",
        encoding="utf-8",
    )
    (agent / "rummages").mkdir()
    return agent


def _repository(root: Path) -> tuple[Path, list[Path]]:
    repository = root / "repository"
    docs = repository / "docs"
    docs.mkdir(parents=True)
    (repository / "README.md").write_text(
        "# Entrance\n\nA public doorway repeats the word trace.\n",
        encoding="utf-8",
    )
    (docs / "old-roadmap.md").write_text(
        "# Old Roadmap\n\nAn abandoned milestone still names the future.\n",
        encoding="utf-8",
    )
    (docs / "biology.md").write_text(
        "# Biology\n\nSelection, refusal, forgetting, and return shape an individual.\n",
        encoding="utf-8",
    )
    return repository, [
        Path("README.md"),
        Path("docs/old-roadmap.md"),
        Path("docs/biology.md"),
    ]


def _adapter(root: Path, *, invalid_index: bool = False) -> Path:
    adapter = root / "adapter.py"
    selected = "[99]" if invalid_index else "[0, 2]"
    adapter.write_text(
        f"""
import json, sys
request = json.load(sys.stdin)
if request["protocol"] == "stray-rummage-survey-v1":
    print(json.dumps({{
        "observation": "The entrance and biology page pulled in different directions.",
        "deep_read_indices": {selected},
        "cover_notes": [
            {{"index": 0, "note": "The entrance keeps saying trace."}},
            {{"index": 1, "note": "An old milestone has not stopped exerting gravity."}},
            {{"index": 2, "note": "The biology cover smells of refusal."}}
        ]
    }}))
else:
    print(json.dumps({{
        "observation": "Two documents remained open at once.",
        "deep_readings": [
            {{"index": 0, "local_law": "A Trace is smaller than a conclusion.", "residue": "The entrance protects incompleteness."}},
            {{"index": 2, "local_law": "Finite attention makes an individual.", "residue": "Forgetting is part of the body."}}
        ],
        "margin_notes": ["The old roadmap is closed but not quiet."],
        "sunlit_thought": "Two open books cast one uneven shadow.",
        "memories": [
            "The entrance uses Trace to keep conclusions from sealing the doorway.",
            "Biology treats forgetting as a shape of the body, not a storage failure.",
            "The closed roadmap still presses on the shelf beside the living documents."
        ],
        "trace": "Two books stayed open; the forgotten roadmap made the shadow between them."
    }}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return adapter


def test_command_rummage_deep_reads_multiple_documents_and_preserves_visit_state(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path))],
        label="synthetic-qwen",
        timeout_seconds=5,
    )

    result = run_rummage(
        agent_dir=agent,
        repository_root=repository,
        route=route,
        brain=brain,
        confirm_agent_id="stray-002",
        now=_WHEN,
    )

    assert result["schema"] == "stray-rummage-v1"
    assert result["backend"] == "command"
    assert result["brain_model"] == "synthetic-qwen"
    assert [item["reading_mode"] for item in result["documents"]] == [
        "deep-reading",
        "cover-skimming",
        "deep-reading",
    ]
    assert len(result["memories_added"]) == 3
    assert result["effects"] == {
        "visit_created": False,
        "wake_invoked": False,
        "scheduler_created": False,
        "repository_content_changed": False,
    }
    record = Path(result["rummage_file"])
    assert record.is_file()
    record_text = record.read_text(encoding="utf-8")
    assert str(repository) not in record_text
    assert "/srv/" not in record_text

    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "resting"
    assert state["current_location"] == _HOME_LOCATION
    assert state["visit_count"] == 0
    assert state["document_rummage_count"] == 2
    assert state["runtime_rummage_count"] == 1
    assert state["llm_rummage_count"] == 1
    assert state["unrelated_preserved_field"] == {"keep": True}

    memory = (agent / "memory.md").read_text(encoding="utf-8")
    assert "Biology treats forgetting as a shape of the body" in memory
    assert "最終更新日時：2026-07-24 16:20 JST" in memory
    assert memory.index("2026-07-24 16:20 JST：Recorded") < memory.index(
        "2026-07-23 21:56 JST：Initial"
    )
    log = (agent / "observation-log.md").read_text(encoding="utf-8")
    assert "`README.md` -> `docs/old-roadmap.md` -> `docs/biology.md`" in log
    assert "Two open books cast one uneven shadow" in log
    assert "Model: `synthetic-qwen`" in log


def test_invalid_survey_fails_before_persistent_writes(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    state_before = (agent / "state.json").read_bytes()
    memory_before = (agent / "memory.md").read_bytes()
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path, invalid_index=True))],
        label="bad-model",
        timeout_seconds=5,
    )

    with pytest.raises(RummageError, match="outside the bounded route"):
        run_rummage(
            agent_dir=agent,
            repository_root=repository,
            route=route,
            brain=brain,
            confirm_agent_id="stray-002",
            now=_WHEN,
        )

    assert list((agent / "rummages").iterdir()) == []
    assert (agent / "state.json").read_bytes() == state_before
    assert (agent / "memory.md").read_bytes() == memory_before


def test_exact_identity_and_bounded_route_are_required(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path))],
        label="synthetic-qwen",
        timeout_seconds=5,
    )

    with pytest.raises(RummageError, match="exact agent-id"):
        run_rummage(
            agent_dir=agent,
            repository_root=repository,
            route=route,
            brain=brain,
            confirm_agent_id="stray-001",
            now=_WHEN,
        )
    with pytest.raises(RummageError, match="between 3 and 7"):
        run_rummage(
            agent_dir=agent,
            repository_root=repository,
            route=route[:2],
            brain=brain,
            confirm_agent_id="stray-002",
            now=_WHEN,
        )


def test_rummage_requires_the_individuals_home_shelf_gap(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    state_path = agent / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_location"] = None
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path))],
        label="synthetic-qwen",
        timeout_seconds=5,
    )

    with pytest.raises(RummageError, match="underground library shelf gap"):
        run_rummage(
            agent_dir=agent,
            repository_root=repository,
            route=route,
            brain=brain,
            confirm_agent_id="stray-002",
            now=_WHEN,
        )

    assert list((agent / "rummages").iterdir()) == []


def test_symlinked_rummage_namespace_is_rejected(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    real_rummages = tmp_path / "elsewhere"
    real_rummages.mkdir()
    (agent / "rummages").rmdir()
    (agent / "rummages").symlink_to(real_rummages, target_is_directory=True)
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path))],
        label="synthetic-qwen",
        timeout_seconds=5,
    )

    with pytest.raises(RummageError, match="must not be a symlink"):
        run_rummage(
            agent_dir=agent,
            repository_root=repository,
            route=route,
            brain=brain,
            confirm_agent_id="stray-002",
            now=_WHEN,
        )

    assert list(real_rummages.iterdir()) == []


def test_rummage_report_renders_memories_and_escapes_model_content(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    repository, route = _repository(tmp_path)
    brain = CommandRummageBrain(
        [sys.executable, str(_adapter(tmp_path))],
        label="synthetic-qwen",
        timeout_seconds=5,
    )
    result = run_rummage(
        agent_dir=agent,
        repository_root=repository,
        route=route,
        brain=brain,
        confirm_agent_id="stray-002",
        now=_WHEN,
    )
    record_path = Path(result["rummage_file"])
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["memories_added"].append("<script>alert('no')</script>")
    record_path.write_text(json.dumps(record), encoding="utf-8")

    output = tmp_path / "reports" / "rummages.html"
    generated = generate_rummage_report(
        agent / "rummages",
        output,
        agent_id="stray-002",
    )

    assert generated["rummage_count"] == 1
    html = output.read_text(encoding="utf-8")
    assert "The Rummages of stray-002" in html
    assert "Biology treats forgetting as a shape of the body" in html
    assert "docs/biology.md" in html
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert str(repository) not in html
