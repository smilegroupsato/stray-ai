from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_source_archive import (
    generate_source_aware_archive,
    resolve_visit_source,
)

_REPOSITORY = "https://github.com/eternal-free-party/free-party-context"
_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40


def _snapshot(tmp_path: Path, commit: str) -> Path:
    root = tmp_path / "venues" / "eternal-free-party" / commit
    root.mkdir(parents=True)
    for name in ("README.md", "REPOSITORY_CONTEXT.md", "AGENTS.md"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "SNAPSHOT.txt").write_text(
        "\n".join(
            [
                f"source_repository={_REPOSITORY}.git",
                "source_branch=main",
                f"source_commit={commit}",
                "captured_at=2026-07-20T12:00:00+09:00",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _legacy_visit(root: Path, tmp_path: Path) -> dict[str, object]:
    return {
        "agent_id": "stray-001",
        "started_at": "2026-07-20T10:44:32+09:00",
        "entrance": str(tmp_path / "legacy" / "README.md"),
        "arrival_path": [
            str(root / "README.md"),
            str(root / "REPOSITORY_CONTEXT.md"),
        ],
        "backend": "mock",
        "steps": [
            {
                "step": 1,
                "location": str(root / "README.md"),
                "title": "Entrance",
                "action": "follow_arrival_path",
            },
            {
                "step": 2,
                "location": str(root / "AGENTS.md"),
                "title": "Agents",
                "action": "leave",
            },
        ],
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
    }


def test_legacy_entrance_falls_back_to_recorded_snapshot_locations(tmp_path: Path) -> None:
    root = _snapshot(tmp_path, _COMMIT_A)
    source = resolve_visit_source(_legacy_visit(root, tmp_path))

    assert source is not None
    assert source.commit == _COMMIT_A
    assert source.repository_url == _REPOSITORY


def test_conflicting_recorded_snapshots_fail_closed(tmp_path: Path) -> None:
    root_a = _snapshot(tmp_path, _COMMIT_A)
    root_b = _snapshot(tmp_path, _COMMIT_B)
    visit = _legacy_visit(root_a, tmp_path)
    visit["steps"] = [
        {
            "step": 1,
            "location": str(root_a / "README.md"),
            "title": "A",
            "action": "follow_link",
        },
        {
            "step": 2,
            "location": str(root_b / "AGENTS.md"),
            "title": "B",
            "action": "leave",
        },
    ]

    assert resolve_visit_source(visit) is None


def test_archive_reports_linked_and_unlinked_filenames(tmp_path: Path) -> None:
    root = _snapshot(tmp_path, _COMMIT_A)
    visits_dir = tmp_path / "agents" / "stray-001" / "visits"
    output_dir = tmp_path / "reports"
    visits_dir.mkdir(parents=True)

    linked = visits_dir / "2026-07-20_104432.json"
    linked.write_text(json.dumps(_legacy_visit(root, tmp_path)), encoding="utf-8")

    unlinked = visits_dir / "2026-07-20_104433.json"
    unlinked_visit = _legacy_visit(root, tmp_path)
    unlinked_visit["entrance"] = str(tmp_path / "plain" / "README.md")
    unlinked_visit["arrival_path"] = []
    unlinked_visit["steps"] = []
    unlinked.write_text(json.dumps(unlinked_visit), encoding="utf-8")

    result = generate_source_aware_archive(visits_dir, output_dir)

    assert result["source_linked_visit_count"] == 1
    assert result["source_linked_visit_files"] == [linked.name]
    assert result["source_unlinked_visit_files"] == [unlinked.name]

    for report_name in ("2026-07-20_104432.html", "2026-07-20_104433.html"):
        soup = BeautifulSoup(
            (output_dir / report_name).read_text(encoding="utf-8"),
            "html.parser",
        )
        assert soup.select_one('.kicker a[href="index.html"]') is not None
