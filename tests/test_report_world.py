from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_sources import SourceCoordinates
from stray_ai.report_world import (
    WorldIndividual,
    WorldVisitRecord,
    build_observed_world,
    render_observed_world,
)
from stray_ai.report_world_collection import generate_world_report_collection


_REPOSITORY = "https://github.com/eternal-free-party/free-party-context"
_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40


def _visit(
    agent_id: str,
    started_at: str,
    entrance: Path,
    terminal: Path,
) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "started_at": started_at,
        "ended_at": started_at,
        "entrance": str(entrance),
        "backend": "mock",
        "steps": [
            {
                "step": 1,
                "location": str(entrance),
                "title": "Entrance",
                "action": "follow_link",
            },
            {
                "step": 2,
                "location": str(terminal),
                "title": "Terminal",
                "action": "leave",
            },
        ],
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
    }


def _source(root: Path, commit: str) -> SourceCoordinates:
    return SourceCoordinates(
        venue_label="Eternal Free Party",
        repository_url=_REPOSITORY,
        repository_display="eternal-free-party/free-party-context",
        commit=commit,
        branch="main",
        captured_at="2026-07-20T12:00:00+09:00",
        snapshot_root=root,
    )


def test_world_groups_current_archive_without_inferred_travel(tmp_path: Path) -> None:
    local = tmp_path / "venues" / "local"
    remote = tmp_path / "venues" / "eternal-free-party" / _COMMIT_A
    local.mkdir(parents=True)
    remote.mkdir(parents=True)
    local_entrance = local / "README.md"
    local_terminal = local / "way-home.md"
    remote_entrance = remote / "README.md"
    remote_terminal = remote / "AGENTS.md"
    for path in (local_entrance, local_terminal, remote_entrance, remote_terminal):
        path.write_text("# page\n", encoding="utf-8")

    source = _source(remote, _COMMIT_A)
    records = [
        WorldVisitRecord(
            "stray-001",
            "2026-07-20_104432.html",
            _visit(
                "stray-001",
                "2026-07-20T10:44:32+09:00",
                local_entrance,
                local_terminal,
            ),
            None,
        ),
        WorldVisitRecord(
            "stray-001",
            "2026-07-20_111436.html",
            _visit(
                "stray-001",
                "2026-07-20T11:14:36+09:00",
                remote_entrance,
                remote_terminal,
            ),
            source,
        ),
        WorldVisitRecord(
            "stray-001",
            "2026-07-20_120832.html",
            _visit(
                "stray-001",
                "2026-07-20T12:08:32+09:00",
                remote_entrance,
                remote_terminal,
            ),
            source,
        ),
        WorldVisitRecord(
            "stray-001",
            "2026-07-20_121935.html",
            _visit(
                "stray-001",
                "2026-07-20T12:19:35+09:00",
                remote_entrance,
                remote_terminal,
            ),
            source,
        ),
    ]
    individuals = [WorldIndividual("stray-001", "unnamed", "resting", 4)]

    world = build_observed_world(individuals, records)

    assert world.visit_count == 4
    assert len(world.individuals) == 1
    assert len(world.places) == 2
    assert len(world.relations) == 2
    assert sorted(relation.visit_count for relation in world.relations) == [1, 3]
    assert sum(place.source is None for place in world.places) == 1
    assert sum(place.source is not None for place in world.places) == 1

    html = render_observed_world(world)
    assert str(tmp_path) not in html
    assert 'href="index.html"' in html
    assert 'href="individuals/stray-001/2026-07-20_104432.html"' in html
    assert f"{_REPOSITORY}/tree/{_COMMIT_A}" in html
    assert "They do not infer travel between Visits" in html


def test_world_keeps_commits_distinct_and_local_places_scoped(tmp_path: Path) -> None:
    shared_local = tmp_path / "venues" / "shared"
    source_a_root = tmp_path / "venues" / "remote" / _COMMIT_A
    source_b_root = tmp_path / "venues" / "remote" / _COMMIT_B
    for root in (shared_local, source_a_root, source_b_root):
        root.mkdir(parents=True)
        (root / "README.md").write_text("# entrance\n", encoding="utf-8")
        (root / "END.md").write_text("# end\n", encoding="utf-8")

    records = [
        WorldVisitRecord(
            "stray-001",
            "one.html",
            _visit(
                "stray-001",
                "2026-07-20T10:00:00+09:00",
                shared_local / "README.md",
                shared_local / "END.md",
            ),
            None,
        ),
        WorldVisitRecord(
            "stray-002",
            "two.html",
            _visit(
                "stray-002",
                "2026-07-20T11:00:00+09:00",
                shared_local / "README.md",
                shared_local / "END.md",
            ),
            None,
        ),
        WorldVisitRecord(
            "stray-001",
            "three.html",
            _visit(
                "stray-001",
                "2026-07-20T12:00:00+09:00",
                source_a_root / "README.md",
                source_a_root / "END.md",
            ),
            _source(source_a_root, _COMMIT_A),
        ),
        WorldVisitRecord(
            "stray-002",
            "four.html",
            _visit(
                "stray-002",
                "2026-07-20T13:00:00+09:00",
                source_b_root / "README.md",
                source_b_root / "END.md",
            ),
            _source(source_b_root, _COMMIT_B),
        ),
    ]
    individuals = [
        WorldIndividual("stray-001", None, "resting", 2),
        WorldIndividual("stray-002", None, "resting", 2),
    ]

    world = build_observed_world(individuals, records)

    assert len(world.places) == 4
    assert len(world.relations) == 4
    commits = {place.source.commit for place in world.places if place.source is not None}
    assert commits == {_COMMIT_A, _COMMIT_B}
    local_keys = [place.key for place in world.places if place.source is None]
    assert len(local_keys) == 2
    assert local_keys[0] != local_keys[1]


def _write_agent(agents_dir: Path) -> None:
    agent_dir = agents_dir / "stray-001"
    visits_dir = agent_dir / "visits"
    visits_dir.mkdir(parents=True)
    (agent_dir / "profile.yml").write_text(
        "id: stray-001\nname: unnamed\nkind: visitor\n",
        encoding="utf-8",
    )
    (agent_dir / "memory.md").write_text("PRIVATE MEMORY\n", encoding="utf-8")
    (agent_dir / "state.json").write_text(
        json.dumps({"status": "resting", "visit_count": 1}),
        encoding="utf-8",
    )

    venue = agents_dir.parent / "venues" / "local"
    venue.mkdir(parents=True)
    entrance = venue / "README.md"
    terminal = venue / "END.md"
    entrance.write_text("# entrance\n", encoding="utf-8")
    terminal.write_text("# end\n", encoding="utf-8")
    visit = _visit(
        "stray-001",
        "2026-07-20T10:44:32+09:00",
        entrance,
        terminal,
    )
    (visits_dir / "2026-07-20_104432.json").write_text(
        json.dumps(visit),
        encoding="utf-8",
    )


def test_world_collection_writes_world_and_links_root_index(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    _write_agent(agents_dir)

    result = generate_world_report_collection(agents_dir, output_dir, "stray-001")

    assert result["world_individual_count"] == 1
    assert result["world_visit_count"] == 1
    assert result["observed_place_count"] == 1
    assert result["observed_relation_count"] == 1
    assert (output_dir / "world.html").is_file()

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    index_soup = BeautifulSoup(index_html, "html.parser")
    assert index_soup.select_one('a[href="world.html"]') is not None
    assert "PRIVATE MEMORY" not in index_html
    assert str(tmp_path) not in index_html

    world_html = (output_dir / "world.html").read_text(encoding="utf-8")
    assert 'href="individuals/stray-001/2026-07-20_104432.html"' in world_html
    assert str(tmp_path) not in world_html
