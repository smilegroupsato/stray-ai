from __future__ import annotations

import json
from pathlib import Path

from stray_ai.report import generate_report, render_report


def _visit() -> dict[str, object]:
    return {
        "agent_id": "stray-001",
        "started_at": "2026-07-20T10:44:32+09:00",
        "entrance": "/venue/README.md",
        "backend": "mock",
        "steps": [
            {
                "step": 1,
                "location": "/venue/README.md",
                "title": "Entrance",
                "action": "follow_link",
            },
            {
                "step": 2,
                "location": "/venue/way-home.md",
                "title": "Way Home",
                "action": "leave",
            },
        ],
        "trace_file": None,
        "memories_added": [],
        "exit_reason": "left_silently",
        "visit_file": "/visits/2026-07-20_104432.json",
    }


def test_render_report_shows_route_and_silence() -> None:
    html = render_report(
        _visit(),
        {
            "status": "awake",
            "visit_count": 1,
            "fatigue": 0.25,
            "current_location": "/venue/way-home.md",
        },
    )

    assert "Visit Report v0" in html
    assert "Entrance" in html
    assert "Way Home" in html
    assert "Left silently" in html
    assert "No trace carried home" in html
    assert "Visit count" in html


def test_render_report_escapes_venue_content() -> None:
    visit = _visit()
    visit["steps"] = [
        {
            "step": 1,
            "location": "/venue/index.md",
            "title": "<script>alert(1)</script>",
            "action": "leave",
        }
    ]

    html = render_report(visit)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_generate_report_writes_named_and_latest_files(tmp_path: Path) -> None:
    visit_path = tmp_path / "2026-07-20_104432.json"
    state_path = tmp_path / "state.json"
    output_dir = tmp_path / "reports"
    visit_path.write_text(json.dumps(_visit()), encoding="utf-8")
    state_path.write_text(json.dumps({"status": "awake", "visit_count": 1}), encoding="utf-8")

    report_path, latest_path = generate_report(visit_path, output_dir, state_path)

    assert report_path.name == "2026-07-20_104432.html"
    assert latest_path.name == "latest.html"
    assert report_path.read_text(encoding="utf-8") == latest_path.read_text(encoding="utf-8")
