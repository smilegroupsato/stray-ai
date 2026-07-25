from __future__ import annotations

import json
from pathlib import Path

import pytest

from stray_ai.report_collection import generate_report_collection
from stray_ai.rummage_visit import (
    RummageVisitError,
    migrate_rummage_visits,
    rummage_to_visit,
)


def _rummage(started_at: str = "2026-07-25T10:16:18+09:00") -> dict[str, object]:
    return {
        "schema": "stray-rummage-v1",
        "agent_id": "stray-002",
        "started_at": started_at,
        "ended_at": started_at,
        "repository": {"name": "stray-ai", "source_commit": "a" * 40},
        "backend": "command",
        "brain_model": "stray-qwen3.5-9b-16k",
        "documents": [
            {
                "path": "README.md",
                "title": "Entrance",
                "reading_mode": "cover-skimming",
                "cover_note": "The doorway remained open.",
            },
            {
                "path": "docs/biology.md",
                "title": "Biology",
                "reading_mode": "deep-reading",
                "deep_reading": {
                    "local_law": "Finite attention makes a visitor.",
                    "residue": "One page stayed open.",
                },
            },
        ],
        "memories_added": ["The shelf remembers finite attention."],
        "trace": "One page stayed open.",
    }


def _agent(tmp_path: Path) -> Path:
    agent = tmp_path / "stray-002"
    (agent / "rummages").mkdir(parents=True)
    (agent / "visits").mkdir()
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "current_location": "damp-underground-library-shelf-gap",
                "visit_count": 0,
            }
        ),
        encoding="utf-8",
    )
    return agent


def test_rummage_projection_is_a_repository_visit() -> None:
    visit = rummage_to_visit(
        _rummage(),
        rummage_record="rummages/2026-07-25_101618.json",
    )

    assert visit["schema"] == "stray-visit-v1"
    assert visit["activity_type"] == "document_rummage"
    assert visit["venue"] == {
        "kind": "repository",
        "id": "repository:stray-ai",
        "label": "stray-ai",
        "source_commit": "a" * 40,
    }
    assert visit["steps"][0]["action"] == "skim_cover"
    assert visit["steps"][1]["action"] == "deep_read"
    assert visit["steps"][-1]["return"] == "damp-underground-library-shelf-gap"
    assert visit["exit_reason"] == "returned_after_document_rummage"


def test_migration_seeds_prototype_and_projects_existing_runtime_rummage(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    runtime = _rummage()
    (agent / "rummages" / "2026-07-25_101618.json").write_text(
        json.dumps(runtime),
        encoding="utf-8",
    )
    seed = tmp_path / "2026-07-23_215600.json"
    seed.write_text(
        json.dumps(
            {
                **rummage_to_visit(
                    {
                        **runtime,
                        "started_at": "2026-07-23T21:56:00+09:00",
                        "ended_at": "2026-07-23T21:56:00+09:00",
                        "backend": "hand-authored",
                        "brain_model": None,
                    },
                    rummage_record="rummages/prototype.json",
                ),
                "record_kind": "hand-authored-prototype",
                "rummage_record": None,
            }
        ),
        encoding="utf-8",
    )

    first = migrate_rummage_visits(agent, seed_visit=seed)
    second = migrate_rummage_visits(agent, seed_visit=seed)

    assert first["created_visit_count"] == 2
    assert second["created_visit_count"] == 0
    assert sorted(path.name for path in (agent / "visits").glob("*.json")) == [
        "2026-07-23_215600.json",
        "2026-07-25_101618.json",
    ]
    state = json.loads((agent / "state.json").read_text(encoding="utf-8"))
    assert state["visit_count"] == 2
    assert state["rummage_visit_count"] == 2
    assert state["llm_visit_count"] == 1
    assert state["current_location"] == "damp-underground-library-shelf-gap"
    assert state["last_visit"] == "2026-07-25T10:16:18+09:00"

    reports = tmp_path / "reports"
    generate_report_collection(agent.parent, reports, "stray-002")
    individual = reports / "individuals" / "stray-002"
    visits_html = (individual / "visits.html").read_text(encoding="utf-8")
    map_html = (individual / "map.html").read_text(encoding="utf-8")
    assert visits_html.count("Document rummage") >= 2
    assert "stray-ai" in map_html
    assert "docs/biology.md" in map_html


def test_migration_rejects_conflicting_existing_visit(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    runtime = _rummage()
    (agent / "rummages" / "2026-07-25_101618.json").write_text(
        json.dumps(runtime),
        encoding="utf-8",
    )
    (agent / "visits" / "2026-07-25_101618.json").write_text(
        json.dumps({"activity_type": "venue_visit"}),
        encoding="utf-8",
    )

    with pytest.raises(RummageVisitError, match="conflicts"):
        migrate_rummage_visits(agent)
