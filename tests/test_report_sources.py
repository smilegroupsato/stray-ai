from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_sources import (
    generate_source_aware_archive,
    resolve_source_coordinates,
)

_COMMIT = "a" * 40
_REPOSITORY = "https://github.com/eternal-free-party/free-party-context"


def _snapshot(tmp_path: Path, *, repository: str = f"{_REPOSITORY}.git") -> Path:
    root = tmp_path / "venues" / "eternal-free-party" / _COMMIT
    root.mkdir(parents=True)
    (root / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (root / "REPOSITORY_CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (root / "SNAPSHOT.txt").write_text(
        "\n".join(
            [
                f"source_repository={repository}",
                "source_branch=main",
                f"source_commit={_COMMIT}",
                "captured_at=2026-07-20T12:00:00+09:00",
                "copied_text_files=3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _visit(root: Path) -> dict[str, object]:
    return {
        "agent_id": "stray-001",
        "started_at": "2026-07-20T12:19:35+09:00",
        "ended_at": "2026-07-20T12:20:31+09:00",
        "entrance": str(root / "README.md"),
        "backend": "command",
        "brain_model": "qwen3.5:9b",
        "steps": [
            {
                "step": 1,
                "location": str(root / "README.md"),
                "title": "Entrance",
                "action": "follow_arrival_path",
            },
            {
                "step": 2,
                "location": str(root / "REPOSITORY_CONTEXT.md"),
                "title": "Repository Context",
                "action": "follow_arrival_path",
            },
            {
                "step": 3,
                "location": str(root / "AGENTS.md"),
                "title": "Agents",
                "action": "leave",
            },
        ],
        "trace_file": None,
        "memories_added": ["A memory"],
        "exit_reason": "left_silently",
    }


def test_resolve_source_coordinates_uses_trusted_snapshot_metadata(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    source = resolve_source_coordinates(_visit(root))

    assert source is not None
    assert source.venue_label == "Eternal Free Party"
    assert source.repository_url == _REPOSITORY
    assert source.repository_display == "eternal-free-party/free-party-context"
    assert source.commit == _COMMIT
    assert source.page_path(root / "AGENTS.md") == "AGENTS.md"
    assert source.page_url(root / "AGENTS.md") == f"{_REPOSITORY}/blob/{_COMMIT}/AGENTS.md"


def test_untrusted_repository_metadata_produces_no_coordinates(tmp_path: Path) -> None:
    root = _snapshot(tmp_path, repository="https://example.invalid/venue.git")

    assert resolve_source_coordinates(_visit(root)) is None


def test_snapshot_directory_must_match_recorded_commit(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    metadata = root / "SNAPSHOT.txt"
    metadata.write_text(
        metadata.read_text(encoding="utf-8").replace(_COMMIT, "b" * 40),
        encoding="utf-8",
    )

    assert resolve_source_coordinates(_visit(root)) is None


def test_source_aware_archive_links_reports_and_exact_pages_without_local_paths(
    tmp_path: Path,
) -> None:
    root = _snapshot(tmp_path)
    visits_dir = tmp_path / "agents" / "stray-001" / "visits"
    output_dir = tmp_path / "reports"
    state_path = tmp_path / "agents" / "stray-001" / "state.json"
    visits_dir.mkdir(parents=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"status": "resting", "visit_count": 1}),
        encoding="utf-8",
    )
    visit_path = visits_dir / "2026-07-20_121935.json"
    visit_path.write_text(json.dumps(_visit(root)), encoding="utf-8")
    before = hashlib.sha256(visit_path.read_bytes()).hexdigest()

    result = generate_source_aware_archive(visits_dir, output_dir, state_path)

    assert result["source_linked_visit_count"] == 1
    assert hashlib.sha256(visit_path.read_bytes()).hexdigest() == before
    report = (output_dir / "2026-07-20_121935.html").read_text(encoding="utf-8")
    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert (output_dir / "latest.html").read_text(encoding="utf-8") == report

    assert f"{_REPOSITORY}/blob/{_COMMIT}/README.md" in report
    assert f"{_REPOSITORY}/blob/{_COMMIT}/REPOSITORY_CONTEXT.md" in report
    assert f"{_REPOSITORY}/blob/{_COMMIT}/AGENTS.md" in report
    assert "Source" in report
    assert "Snapshot captured" in report
    assert str(tmp_path) not in report

    soup = BeautifulSoup(index, "html.parser")
    local = soup.select_one('.visit-main h2 a[href="2026-07-20_121935.html"]')
    external = soup.select_one(f'a[href="{_REPOSITORY}"]')
    assert local is not None
    assert external is not None
    assert external.get("target") == "_blank"
    assert str(tmp_path) not in index


def test_page_paths_are_percent_encoded(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    page = root / "notes" / "日本 語.md"
    page.parent.mkdir()
    page.write_text("# Note\n", encoding="utf-8")
    visit = _visit(root)
    visit["steps"] = [
        {
            "step": 1,
            "location": str(page),
            "title": "Note",
            "action": "leave",
        }
    ]
    source = resolve_source_coordinates(visit)

    assert source is not None
    assert source.page_url(page) == (
        f"{_REPOSITORY}/blob/{_COMMIT}/notes/%E6%97%A5%E6%9C%AC%20%E8%AA%9E.md"
    )
