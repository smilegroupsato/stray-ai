from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_map import (
    augment_index_with_map_link,
    build_observed_map,
    render_observed_map,
)
from stray_ai.report_source_archive import generate_source_aware_archive
from stray_ai.report_sources import SourceCoordinates


_REPOSITORY = "https://github.com/eternal-free-party/free-party-context"
_COMMIT = "a" * 40


def _step(path: Path, title: str, action: str = "follow_link") -> dict[str, object]:
    return {
        "location": str(path),
        "title": title,
        "action": action,
    }


def _visit(
    started_at: str,
    entrance: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "agent_id": "stray-001",
        "started_at": started_at,
        "entrance": str(entrance),
        "backend": "mock",
        "steps": steps,
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
    }


def _current_records(
    tmp_path: Path,
) -> tuple[
    dict[str, tuple[dict[str, object], SourceCoordinates | None]],
    Path,
    Path,
]:
    local = tmp_path / "data" / "venues"
    local.mkdir(parents=True)
    local_pages = [
        local / "README.md",
        local / "faded-notice.md",
        local / "empty-bench.md",
        local / "way-home.md",
    ]
    for page in local_pages:
        page.write_text(f"# {page.name}\n", encoding="utf-8")

    source_root = tmp_path / "data" / "venues" / "eternal-free-party" / _COMMIT
    (source_root / "docs").mkdir(parents=True)
    source_pages = [
        source_root / "README.md",
        source_root / "REPOSITORY_CONTEXT.md",
        source_root / "AGENTS.md",
        source_root / "docs" / "becoming.md",
    ]
    for page in source_pages:
        page.write_text(f"# {page.name}\n", encoding="utf-8")

    source = SourceCoordinates(
        venue_label="Eternal Free Party",
        repository_url=_REPOSITORY,
        repository_display="eternal-free-party/free-party-context",
        commit=_COMMIT,
        branch="main",
        captured_at="2026-07-20T12:00:00+09:00",
        snapshot_root=source_root,
    )

    records: dict[str, tuple[dict[str, object], SourceCoordinates | None]] = {
        "2026-07-20_104432.html": (
            _visit(
                "2026-07-20T10:44:32+09:00",
                local_pages[0],
                [
                    _step(local_pages[0], "Entrance"),
                    _step(local_pages[1], "Faded Notice"),
                    _step(local_pages[2], "Empty Bench"),
                    _step(local_pages[3], "Way Home", "leave"),
                ],
            ),
            None,
        ),
        "2026-07-20_111436.html": (
            _visit(
                "2026-07-20T11:14:36+09:00",
                source_pages[0],
                [
                    _step(source_pages[0], "Entrance"),
                    _step(source_pages[3], "Becoming", "leave"),
                ],
            ),
            source,
        ),
        "2026-07-20_120832.html": (
            _visit(
                "2026-07-20T12:08:32+09:00",
                source_pages[0],
                [
                    _step(source_pages[0], "Entrance"),
                    _step(source_pages[1], "Repository Context"),
                    _step(source_pages[2], "Agents", "leave"),
                ],
            ),
            source,
        ),
        "2026-07-20_121935.html": (
            _visit(
                "2026-07-20T12:19:35+09:00",
                source_pages[0],
                [
                    _step(source_pages[0], "Entrance"),
                    _step(source_pages[1], "Repository Context"),
                    _step(source_pages[2], "Agents", "leave"),
                ],
            ),
            source,
        ),
    }
    return records, local, source_root


def test_observed_map_groups_current_archive_and_aggregates_routes(tmp_path: Path) -> None:
    records, _, _ = _current_records(tmp_path)

    observed = build_observed_map(records)

    assert observed.visit_count == 4
    assert len(observed.venues) == 2
    assert observed.node_count == 8
    assert observed.edge_count == 6

    local, eternal = observed.venues
    assert local.label == "Local first habitat"
    assert len(local.routes) == 1
    assert len(local.nodes) == 4
    assert local.source is None

    assert eternal.label == "Eternal Free Party"
    assert len(eternal.routes) == 3
    assert len(eternal.nodes) == 4
    assert eternal.source is not None

    by_path = {node.display_path: node for node in eternal.nodes.values()}
    assert len(by_path["README.md"].visit_files) == 3
    assert len(by_path["REPOSITORY_CONTEXT.md"].visit_files) == 2
    assert len(by_path["AGENTS.md"].visit_files) == 2
    assert len(by_path["docs/becoming.md"].visit_files) == 1

    edge_paths = {
        (
            eternal.nodes[left].display_path,
            eternal.nodes[right].display_path,
        ): count
        for (left, right), count in eternal.edges.items()
    }
    assert edge_paths[("README.md", "REPOSITORY_CONTEXT.md")] == 2
    assert edge_paths[("REPOSITORY_CONTEXT.md", "AGENTS.md")] == 2
    assert edge_paths[("README.md", "docs/becoming.md")] == 1


def test_rendered_map_has_relative_reports_exact_sources_and_no_local_paths(
    tmp_path: Path,
) -> None:
    records, _, _ = _current_records(tmp_path)
    html = render_observed_map(build_observed_map(records))

    assert str(tmp_path) not in html
    assert 'href="index.html"' in html
    assert 'href="2026-07-20_104432.html"' in html
    assert 'href="2026-07-20_121935.html"' in html
    assert f"{_REPOSITORY}/blob/{_COMMIT}/AGENTS.md" in html
    assert f"{_REPOSITORY}/blob/{_COMMIT}/docs/becoming.md" in html
    assert "Local-only observation · no external source coordinates" in html
    assert "2×" in html
    assert "Unvisited pages" in html


def test_rendered_map_uses_shared_terminal_identity_and_safe_static_ui(
    tmp_path: Path,
) -> None:
    records, _, _ = _current_records(tmp_path)
    html = render_observed_map(build_observed_map(records))
    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("h1", string="Observed Venue Map")
    assert title is not None
    assert title.find_previous_sibling("svg", class_="stray-mark") is not None
    assert soup.select_one("main.terminal-shell.observed-map-shell") is not None
    assert soup.select_one("header.title-zone") is not None
    assert soup.select_one('link[rel="icon"][href^="data:image/svg+xml,"]') is not None
    assert soup.select_one("section.map-summary") is not None
    assert len(soup.select("section.venue-sector")) == 2
    assert len(soup.select(".graph-enclosure svg.venue-svg")) == 2
    assert len(soup.select(".evidence-table.route-evidence")) == 2
    assert len(soup.select(".evidence-table.page-evidence")) == 2

    assert "STRAY // OBSERVATION TERMINAL" in html
    assert "linear-gradient(rgba(57,246,255,.035) 1px,transparent 1px)" in html
    assert "repeating-linear-gradient(0deg" in html
    assert "body::after" in html
    assert "url(http" not in html
    assert "Current Board" not in html

    lowered = html.lower()
    for forbidden in (
        "<script",
        "<button",
        "<form",
        "javascript:",
        "file://",
        "/srv/",
        "snapshot_root",
        "brain_command",
    ):
        assert forbidden not in lowered


def test_rendered_map_preserves_graph_accessibility_and_link_safety(
    tmp_path: Path,
) -> None:
    records, _, _ = _current_records(tmp_path)
    html = render_observed_map(build_observed_map(records))
    soup = BeautifulSoup(html, "html.parser")

    graphs = soup.select('svg.venue-svg[role="img"][aria-labelledby]')
    assert len(graphs) == 2
    for graph in graphs:
        title_id = graph["aria-labelledby"]
        assert graph.find("title", id=title_id) is not None

    external_links = soup.select('a[target="_blank"]')
    assert external_links
    for link in external_links:
        assert link.get("rel") == ["noopener", "noreferrer"]
        assert str(link["href"]).startswith(f"{_REPOSITORY}")

    exact_page = f"{_REPOSITORY}/blob/{_COMMIT}/AGENTS.md"
    assert soup.select_one(f'a[href="{exact_page}"]') is not None
    local_hrefs = {
        link["href"]
        for link in soup.select("a[href]")
        if not str(link["href"]).startswith("https://")
    }
    assert "index.html" in local_hrefs
    assert "2026-07-20_104432.html" in local_hrefs
    assert all(not str(href).startswith("/") for href in local_hrefs)


def test_empty_map_preserves_observed_absence() -> None:
    html = render_observed_map(build_observed_map({}))

    assert "No observed route has entered the map yet." in html
    assert "Observed venues</span><strong>0</strong>" in html
    assert 'href="index.html"' in html


def test_index_map_link_is_relative_and_idempotent() -> None:
    html = '<html><head></head><body><div class="archive-head"><h2>Visits</h2></div></body></html>'

    once = augment_index_with_map_link(html)
    twice = augment_index_with_map_link(once)

    soup = BeautifulSoup(twice, "html.parser")
    links = soup.select('a[href="map.html"]')
    assert len(links) == 1
    assert "Observed venue map" in links[0].get_text()


def test_source_aware_archive_writes_map_and_links_index(tmp_path: Path) -> None:
    visits_dir = tmp_path / "agents" / "stray-001" / "visits"
    output_dir = tmp_path / "reports"
    snapshot = tmp_path / "venues" / "eternal-free-party" / _COMMIT
    snapshot.mkdir(parents=True)
    for name in ("README.md", "AGENTS.md"):
        (snapshot / name).write_text(f"# {name}\n", encoding="utf-8")
    (snapshot / "SNAPSHOT.txt").write_text(
        "\n".join(
            [
                f"source_repository={_REPOSITORY}.git",
                "source_branch=main",
                f"source_commit={_COMMIT}",
                "captured_at=2026-07-20T12:00:00+09:00",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    visits_dir.mkdir(parents=True)
    visit = _visit(
        "2026-07-20T12:19:35+09:00",
        snapshot / "README.md",
        [
            _step(snapshot / "README.md", "Entrance"),
            _step(snapshot / "AGENTS.md", "Agents", "leave"),
        ],
    )
    (visits_dir / "2026-07-20_121935.json").write_text(
        json.dumps(visit), encoding="utf-8"
    )

    result = generate_source_aware_archive(visits_dir, output_dir)

    assert Path(result["map_file"]).name == "map.html"
    assert result["observed_venue_count"] == 1
    assert result["observed_node_count"] == 2
    assert result["observed_edge_count"] == 1
    assert (output_dir / "map.html").is_file()
    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="map.html"' in index
