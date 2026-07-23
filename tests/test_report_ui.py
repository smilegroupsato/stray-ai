from __future__ import annotations

from bs4 import BeautifulSoup

from stray_ai.report import render_report
from stray_ai.report_navigation import add_archive_link
from stray_ai.report_presentation import localize_visit_report


def _visit() -> dict[str, object]:
    return {
        "agent_id": "stray-001",
        "started_at": "2026-07-21T13:05:24+09:00",
        "entrance": "/venue/README.md",
        "backend": "command",
        "brain_model": "qwen3.5:9b",
        "steps": [
            {
                "step": 1,
                "location": "/venue/README.md",
                "title": "Entrance",
                "action": "follow_arrival_path",
                "brain": {
                    "status": "not_invoked",
                    "model": "qwen3.5:9b",
                    "observation": "Trusted reception path selected by the host.",
                    "error": None,
                },
            },
            {
                "step": 2,
                "location": "/venue/AFTERHOURS.md",
                "title": "AFTERHOURS.md",
                "action": "leave",
                "brain": {
                    "status": "accepted",
                    "model": "qwen3.5:9b",
                    "observation": "The silence feels complete.",
                    "error": None,
                },
            },
        ],
        "trace_file": None,
        "memories_added": ["An exact memory that must not be translated."],
        "exit_reason": "left_silently",
        "visit_file": "/visits/2026-07-21_130524.json",
    }


def test_localizes_labels_without_translating_recorded_text() -> None:
    source = add_archive_link(
        render_report(
            _visit(),
            {
                "status": "resting",
                "visit_count": 5,
                "fatigue": 0.25,
                "current_location": None,
            },
        )
    )

    html = localize_visit_report(source)
    soup = BeautifulSoup(html, "html.parser")
    archive_link = soup.select_one(".kicker a")

    assert archive_link is not None
    assert archive_link.get_text(strip=True) == "Stray AI · 訪問レポート v0"
    assert [heading.get_text(strip=True) for heading in soup.select(".panel h2")] == [
        "歩いた経路",
        "訪問",
        "判断",
        "持ち帰ったもの",
        "現在の状態",
        "記録",
    ]
    for label in (
        "ステップ 1",
        "退出",
        "Trace / 痕跡",
        "記憶",
        "新しい記憶",
        "休息中",
        "受理",
        "未実行",
    ):
        assert label in html

    assert "Trusted reception path selected by the host." in html
    assert "The silence feels complete." in html
    assert "An exact memory that must not be translated." in html


def test_adds_narrow_window_layout_guards() -> None:
    html = localize_visit_report(render_report(_visit()))
    soup = BeautifulSoup(html, "html.parser")

    assert "html,body{min-width:0;overflow-x:hidden}" in html
    assert "grid-template-columns:minmax(0,2fr) minmax(260px,1fr)" in html
    assert "@media(max-width:1120px)" in html
    assert ".grid{grid-template-columns:minmax(0,1fr)}" in html
    assert "@media(max-width:680px)" in html
    assert ".route{display:grid;grid-template-columns:minmax(0,1fr)" in html
    title = soup.select_one("header .title-row h1")
    assert title is not None
    assert title.find_previous_sibling("svg", class_="stray-mark") is not None
    assert soup.select_one('link[rel="icon"][href^="data:image/svg+xml,"]') is not None
    assert "--bg-0:#05070b" in html
    assert "--cyan:#39f6ff" in html
    assert soup.select_one("main.terminal-shell.visit-report-shell") is not None
    assert soup.select_one("header.title-zone") is not None
    assert soup.select_one(".brain-records.evidence-module") is not None
    assert soup.select_one(".brain-card.observation-record") is not None
    assert soup.select_one(".trace-memory-module.evidence-module") is not None
    assert soup.select_one(".current-state-module.evidence-module") is not None
    assert "repeating-linear-gradient" in html
    assert "url(http" not in html
    assert "Current Board" not in html
    assert "/current/" not in html
    for marker in (
        "<script",
        "<button",
        "<form",
        "javascript:",
        "file://",
        "/srv/",
        "snapshot_root",
        "brain_command",
    ):
        assert marker not in html.lower()
