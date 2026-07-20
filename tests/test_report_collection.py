from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from stray_ai.report_collection import generate_report_collection


def _write_agent(
    agents_dir: Path,
    agent_id: str,
    *,
    name: str,
    status: str,
    visit_stem: str,
    started_at: str,
    page_prefix: str,
) -> Path:
    agent_dir = agents_dir / agent_id
    visits_dir = agent_dir / "visits"
    visits_dir.mkdir(parents=True)
    (agent_dir / "profile.yml").write_text(
        f"id: {agent_id}\nname: {name}\nkind: visitor\n",
        encoding="utf-8",
    )
    (agent_dir / "memory.md").write_text(
        f"PRIVATE MEMORY FOR {agent_id}\n",
        encoding="utf-8",
    )
    (agent_dir / "state.json").write_text(
        json.dumps({"status": status, "visit_count": 1}),
        encoding="utf-8",
    )

    venue = agents_dir.parent / "venues" / agent_id
    entrance = venue / f"{page_prefix}-entrance.md"
    terminal = venue / f"{page_prefix}-terminal.md"
    visit = {
        "agent_id": agent_id,
        "started_at": started_at,
        "ended_at": started_at,
        "entrance": str(entrance),
        "backend": "mock",
        "steps": [
            {
                "step": 1,
                "location": str(entrance),
                "title": f"{page_prefix} Entrance",
                "action": "follow_link",
            },
            {
                "step": 2,
                "location": str(terminal),
                "title": f"{page_prefix} Terminal",
                "action": "leave",
            },
        ],
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
    }
    (visits_dir / f"{visit_stem}.json").write_text(
        json.dumps(visit),
        encoding="utf-8",
    )
    return agent_dir


def test_collection_keeps_two_individuals_isolated_and_preserves_primary_aliases(
    tmp_path: Path,
) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    _write_agent(
        agents_dir,
        "stray-001",
        name="unnamed",
        status="resting",
        visit_stem="2026-07-20_104432",
        started_at="2026-07-20T10:44:32+09:00",
        page_prefix="Alpha",
    )
    _write_agent(
        agents_dir,
        "stray-002",
        name="second visitor",
        status="awake",
        visit_stem="2026-07-21_091500",
        started_at="2026-07-21T09:15:00+09:00",
        page_prefix="Beta",
    )

    output_dir.mkdir(parents=True)
    (output_dir / "2020-01-01_000000.html").write_text("stale", encoding="utf-8")
    stale_namespace = output_dir / "individuals" / "removed-agent"
    stale_namespace.mkdir(parents=True)
    (stale_namespace / "index.html").write_text("stale", encoding="utf-8")

    result = generate_report_collection(
        agents_dir,
        output_dir,
        primary_agent_id="stray-001",
    )

    assert result["individual_count"] == 2
    assert result["total_visit_count"] == 2
    assert result["primary_agent_id"] == "stray-001"
    assert result["skipped_agent_directories"] == []
    assert [item["agent_id"] for item in result["individuals"]] == [
        "stray-001",
        "stray-002",
    ]

    first = output_dir / "individuals" / "stray-001"
    second = output_dir / "individuals" / "stray-002"
    for directory, report_name in (
        (first, "2026-07-20_104432.html"),
        (second, "2026-07-21_091500.html"),
    ):
        assert (directory / "index.html").is_file()
        assert (directory / "latest.html").is_file()
        assert (directory / "map.html").is_file()
        assert (directory / report_name).is_file()

    assert not stale_namespace.exists()
    assert not (output_dir / "2020-01-01_000000.html").exists()

    assert (output_dir / "visits.html").read_bytes() == (
        first / "index.html"
    ).read_bytes()
    assert (output_dir / "latest.html").read_bytes() == (
        first / "latest.html"
    ).read_bytes()
    assert (output_dir / "map.html").read_bytes() == (first / "map.html").read_bytes()
    assert (output_dir / "2026-07-20_104432.html").is_file()
    assert not (output_dir / "2026-07-21_091500.html").exists()

    root_index = (output_dir / "index.html").read_text(encoding="utf-8")
    root_soup = BeautifulSoup(root_index, "html.parser")
    assert root_soup.select_one(
        'a[href="individuals/stray-001/index.html"]'
    ) is not None
    assert root_soup.select_one(
        'a[href="individuals/stray-002/index.html"]'
    ) is not None
    assert root_soup.select_one(
        'a[href="individuals/stray-001/latest.html"]'
    ) is not None
    assert root_soup.select_one(
        'a[href="individuals/stray-002/map.html"]'
    ) is not None
    assert "PRIVATE MEMORY" not in root_index
    assert str(tmp_path) not in root_index

    first_map = (first / "map.html").read_text(encoding="utf-8")
    second_map = (second / "map.html").read_text(encoding="utf-8")
    root_map = (output_dir / "map.html").read_text(encoding="utf-8")
    assert "Alpha Entrance" in first_map
    assert "Beta Entrance" not in first_map
    assert "Beta Entrance" in second_map
    assert "Alpha Entrance" not in second_map
    assert "Alpha Entrance" in root_map
    assert "Beta Entrance" not in root_map
    assert str(tmp_path) not in first_map
    assert str(tmp_path) not in second_map


def test_collection_escapes_profile_and_state_metadata(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    _write_agent(
        agents_dir,
        "stray-001",
        name="<script>alert(1)</script>",
        status="<b>resting</b>",
        visit_stem="2026-07-20_104432",
        started_at="2026-07-20T10:44:32+09:00",
        page_prefix="Alpha",
    )

    generate_report_collection(agents_dir, output_dir, "stray-001")
    html = (output_dir / "index.html").read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>resting</b>" not in html
    assert "&lt;b&gt;resting&lt;/b&gt;" in html


def test_collection_skips_unsafe_namespaces(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    _write_agent(
        agents_dir,
        "stray-001",
        name="unnamed",
        status="resting",
        visit_stem="2026-07-20_104432",
        started_at="2026-07-20T10:44:32+09:00",
        page_prefix="Alpha",
    )
    unsafe = agents_dir / "bad agent"
    unsafe.mkdir(parents=True)
    (unsafe / "state.json").write_text("{}", encoding="utf-8")

    result = generate_report_collection(agents_dir, output_dir, "stray-001")

    assert result["individual_count"] == 1
    assert result["skipped_agent_directories"] == ["bad agent"]
    assert not (output_dir / "individuals" / "bad agent").exists()


def test_missing_explicit_primary_fails_before_generated_tree_is_replaced(
    tmp_path: Path,
) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    _write_agent(
        agents_dir,
        "stray-001",
        name="unnamed",
        status="resting",
        visit_stem="2026-07-20_104432",
        started_at="2026-07-20T10:44:32+09:00",
        page_prefix="Alpha",
    )
    sentinel = output_dir / "individuals" / "sentinel.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="stray-999"):
        generate_report_collection(agents_dir, output_dir, "stray-999")

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_empty_collection_is_truthful_and_has_no_primary_aliases(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    output_dir = tmp_path / "reports"
    agents_dir.mkdir()
    output_dir.mkdir()
    for name in ("latest.html", "map.html", "visits.html"):
        (output_dir / name).write_text("stale", encoding="utf-8")

    result = generate_report_collection(agents_dir, output_dir)

    assert result["individual_count"] == 0
    assert result["primary_agent_id"] is None
    assert result["compatibility_files"] == []
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "No persistent individuals observed" in html
    assert "No individual was created or awakened" in html
    assert not (output_dir / "latest.html").exists()
    assert not (output_dir / "map.html").exists()
    assert not (output_dir / "visits.html").exists()
