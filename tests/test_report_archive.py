from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_archive import generate_archive, render_index


def _visit(
    started_at: str,
    *,
    backend: str = "mock",
    model: str | None = None,
    exit_reason: str = "left_silently",
    trace: bool = False,
) -> dict[str, object]:
    stamp = started_at[:19].replace(":", "").replace("T", "_")
    return {
        "agent_id": "stray-001",
        "started_at": started_at,
        "ended_at": started_at,
        "entrance": (
            "/srv/sgos/data/stray-ai/venues/eternal-free-party/"
            "ae3bdba670c87b0057bb85730e8f928fd95cee4b/README.md"
        ),
        "backend": backend,
        "brain_model": model,
        "steps": [
            {
                "step": 1,
                "location": "/venue/README.md",
                "title": "Entrance",
                "action": "leave",
            }
        ],
        "trace_file": f"/outbox/{stamp}.md" if trace else None,
        "memories_added": ["one memory"] if model else [],
        "exit_reason": exit_reason,
    }


def _write_visit(visits_dir: Path, name: str, visit: dict[str, object]) -> Path:
    path = visits_dir / name
    path.write_text(json.dumps(visit), encoding="utf-8")
    return path


def test_generate_archive_renders_all_reports_index_and_latest(tmp_path: Path) -> None:
    visits_dir = tmp_path / "visits"
    output_dir = tmp_path / "reports"
    state_path = tmp_path / "state.json"
    visits_dir.mkdir()
    state_path.write_text(
        json.dumps({"status": "resting", "visit_count": 2}),
        encoding="utf-8",
    )
    older = _write_visit(
        visits_dir,
        "2026-07-20_104432.json",
        _visit("2026-07-20T10:44:32+09:00"),
    )
    newer = _write_visit(
        visits_dir,
        "2026-07-20_121935.json",
        _visit(
            "2026-07-20T12:19:35+09:00",
            backend="command",
            model="qwen3.5:9b",
            trace=True,
        ),
    )

    result = generate_archive(visits_dir, output_dir, state_path)

    assert result["visit_count"] == 2
    assert result["skipped_visit_files"] == []
    assert (output_dir / f"{older.stem}.html").exists()
    assert (output_dir / f"{newer.stem}.html").exists()
    assert (output_dir / "index.html").exists()
    assert (output_dir / "latest.html").read_text(encoding="utf-8") == (
        output_dir / f"{newer.stem}.html"
    ).read_text(encoding="utf-8")

    index = (output_dir / "index.html").read_text(encoding="utf-8")
    newer_link = 'href="2026-07-20_121935.html"'
    older_link = 'href="2026-07-20_104432.html"'
    assert index.index(newer_link) < index.index(older_link)
    assert "The Visits of stray-001" in index
    assert "Eternal Free Party" in index
    assert "resting" in index
    assert "qwen3.5:9b" in index
    assert "LATEST" in index
    assert not BeautifulSoup(index, "html.parser").select(
        'a[href^="http://"],a[href^="https://"],link[href^="http://"],link[href^="https://"]'
    )

    soup = BeautifulSoup(index, "html.parser")
    title = soup.select_one("header .title-row h1")
    assert title is not None
    assert title.find_previous_sibling("svg", class_="stray-mark") is not None
    assert soup.select_one('link[rel="icon"][href^="data:image/svg+xml,"]') is not None
    assert "--bg-0:#05070b" in index
    assert "--magenta:#ff4fd8" in index
    assert "Current Board" not in index
    assert "/current/" not in index


def test_generate_archive_skips_malformed_json_without_blocking_valid_record(
    tmp_path: Path,
) -> None:
    visits_dir = tmp_path / "visits"
    output_dir = tmp_path / "reports"
    visits_dir.mkdir()
    _write_visit(
        visits_dir,
        "2026-07-20_104432.json",
        _visit("2026-07-20T10:44:32+09:00"),
    )
    (visits_dir / "2026-07-20_120832.json").write_text("{not json", encoding="utf-8")

    result = generate_archive(visits_dir, output_dir)

    assert result["visit_count"] == 1
    assert result["skipped_visit_files"] == ["2026-07-20_120832.json"]
    assert (output_dir / "2026-07-20_104432.html").exists()
    assert (output_dir / "index.html").exists()


def test_generate_empty_archive_writes_index_and_removes_stale_latest(tmp_path: Path) -> None:
    visits_dir = tmp_path / "visits"
    output_dir = tmp_path / "reports"
    visits_dir.mkdir()
    output_dir.mkdir()
    (output_dir / "latest.html").write_text("stale", encoding="utf-8")

    result = generate_archive(visits_dir, output_dir)

    assert result["visit_count"] == 0
    assert result["latest_report"] is None
    assert not (output_dir / "latest.html").exists()
    index = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "No visit has entered the archive yet" in index


def test_render_index_escapes_record_derived_strings() -> None:
    visit = _visit("2026-07-20T12:19:35+09:00", model="<script>x</script>")
    visit["entrance"] = '/venue/<img src=x onerror=alert(1)>/README.md'
    path = Path("2026-07-20_121935.json")

    html = render_index([(path, visit)], {"status": "<b>awake</b>"})

    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<b>awake</b>" not in html
    assert "&lt;b&gt;awake&lt;/b&gt;" in html
    assert "<img src=x onerror=alert(1)>" not in html
