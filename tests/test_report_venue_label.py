from __future__ import annotations

from pathlib import Path

from stray_ai.report_sources import resolve_source_coordinates


COMMIT = "b" * 40
REPOSITORY = "https://github.com/smilegroupsato/web-genai-ron-jp.git"


def test_trusted_snapshot_can_supply_display_label(tmp_path: Path) -> None:
    root = tmp_path / "venues" / "genai-ron-rc" / COMMIT
    root.mkdir(parents=True)
    (root / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (root / "SNAPSHOT.txt").write_text(
        "venue_label=GENAI-RON Repository Context\n"
        f"source_repository={REPOSITORY}\n"
        "source_branch=main\n"
        f"source_commit={COMMIT}\n",
        encoding="utf-8",
    )
    visit = {
        "agent_id": "stray-001",
        "started_at": "2026-07-21T12:00:00+09:00",
        "entrance": str(root / "README.md"),
        "steps": [],
    }

    source = resolve_source_coordinates(visit)

    assert source is not None
    assert source.venue_label == "GENAI-RON Repository Context"
