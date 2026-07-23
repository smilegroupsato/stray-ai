from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

from stray_ai.current_board import CurrentBoardError, load_current_board, publish_current_board

_JST = ZoneInfo("Asia/Tokyo")


def _board(path: Path, *, now: str = "mapping") -> Path:
    now_block = (
        """
now:
  title: Multi-Venue Wake Selection v0
  purpose: 本人が安全に次の候補を選べるようにする
  stage: design
  next_action: Issueと安全境界を確定する
  implementation_authorized: false
  notes:
    - Venue本文は読まない
"""
        if now == "mapping"
        else "\nnow: []\n"
    )
    path.write_text(
        "schema_version: 0.1\n"
        "title: Stray AI Current Board\n"
        "updated_at: 2026-07-23\n"
        + now_block
        + """
next:
  - 設計レビュー
hold:
  - title: Console link
    detail: Console成立後
recently_done:
  - title: 完了済み基盤
    detail: 安全な訪問のための基礎機能群
    children:
      - title: Venue-scoped wake comparison
        detail: Venue本文を読まずに候補を比較する
parking_lot:
  - title: EFP SNS投稿
    items:
      - Bluesky
      - Mastodon
not_doing:
  - automatic wake
""",
        encoding="utf-8",
    )
    return path


def _agent(path: Path) -> Path:
    path.mkdir()
    (path / "state.json").write_text(
        json.dumps(
            {
                "id": "stray-001",
                "status": "resting",
                "current_location": None,
                "last_location": "/srv/private/venue/README.md",
                "visit_count": 5,
            }
        ),
        encoding="utf-8",
    )
    wake_dir = path / "wake_checks"
    wake_dir.mkdir()
    (wake_dir / "2026-07-21_100000.json").write_text("not-json", encoding="utf-8")
    (wake_dir / "2026-07-22_154209.json").write_text(
        json.dumps(
            {
                "checked_at": "2026-07-22T15:42:09+09:00",
                "decision": "remain_asleep",
                "venue": {
                    "candidate_venue_id": "eternal-free-party",
                    "comparison_scope": "same_venue_history",
                },
            }
        ),
        encoding="utf-8",
    )
    request_dir = path / "visit_requests"
    request_dir.mkdir()
    (request_dir / "pending.json").write_text(
        json.dumps(
            {
                "status": "pending_human_approval",
                "snapshot_root": "/srv/private",
            }
        ),
        encoding="utf-8",
    )
    (request_dir / "broken.json").write_text("{", encoding="utf-8")
    return path


def test_publish_combines_plan_and_live_state_without_exposing_local_paths(
    tmp_path: Path,
) -> None:
    board = _board(tmp_path / "board.yml")
    agent = _agent(tmp_path / "agent")
    reports = tmp_path / "reports"
    reports.mkdir()

    result = publish_current_board(
        board_path=board,
        agent_dir=agent,
        report_root=reports,
        generated_at=datetime(2026, 7, 23, 10, 0, tzinfo=_JST),
    )

    output = reports / "current" / "index.html"
    rendered = output.read_text(encoding="utf-8")
    assert result["gateway_path"] == "/stray-ai/current/index.html"
    assert result["now"] == "Multi-Venue Wake Selection v0"
    assert result["pending_request_count"] == 1
    assert result["visit_count"] == 5
    assert "stray-001" in rendered
    assert "remain_asleep" in rendered
    assert "eternal-free-party" in rendered
    assert "INVALID LOCAL RECORDS" in rendered
    assert ">2<" in rendered
    assert "/srv/" not in rendered
    assert "snapshot_root" not in rendered
    assert "brain_command" not in rendered
    assert "<button" not in rendered.lower()
    assert "<form" not in rendered.lower()
    assert "<script" not in rendered.lower()
    assert "javascript:" not in rendered.lower()
    assert "file://" not in rendered.lower()
    assert list((reports / "current").iterdir()) == [output]

    soup = BeautifulSoup(rendered, "html.parser")
    purpose = soup.select_one(".now-purpose")
    assert purpose is not None
    assert purpose.get_text(strip=True) == "本人が安全に次の候補を選べるようにする"
    assert purpose.find_parent("ul") is None
    assert "本人が安全に次の候補を選べるようにする" not in (
        soup.select_one(".now-notes").get_text(" ", strip=True)
    )
    assert purpose.find_previous("h3") is not None
    assert purpose.find_next(class_="now-grid") is not None

    group = soup.select_one(".done .board-group")
    assert group is not None
    assert len(soup.select(".done > ul > .board-group")) == 1
    assert group.select_one(".board-group-title").get_text(strip=True) == "完了済み基盤"
    child = group.select_one(".board-children > .board-child")
    assert child is not None
    assert "Venue-scoped wake comparison" in child.get_text(" ", strip=True)
    assert "Venue本文を読まずに候補を比較する" in child.get_text(" ", strip=True)

    title = soup.select_one("header .title-row h1")
    assert title is not None
    assert title.find_previous_sibling("svg", class_="stray-mark") is not None
    assert soup.select_one('link[rel="icon"][href^="data:image/svg+xml,"]') is not None
    assert len(soup.select('a[href="../index.html"]')) == 1
    assert soup.select_one('a[href="../index.html"] [role="button"]') is None
    assert "--bg-0:#05070b" in rendered
    assert "--cyan:#39f6ff" in rendered
    assert soup.select_one("main.terminal-shell.current-board-shell") is not None
    assert soup.select_one("header.title-zone") is not None
    assert "repeating-linear-gradient" in rendered
    assert "body::before" in rendered
    assert "url(http" not in rendered
    for section_class in ("next", "hold", "done", "parking", "not-doing"):
        assert soup.select_one(f".panel.{section_class}") is not None
    assert "@media (max-width: 820px)" in rendered


def test_now_must_be_exactly_one_mapping(tmp_path: Path) -> None:
    board = _board(tmp_path / "board.yml", now="list")
    with pytest.raises(CurrentBoardError, match="exactly one NOW mapping"):
        load_current_board(board)


@pytest.mark.parametrize("purpose", ["[]", "{}"])
def test_now_purpose_must_be_a_non_empty_scalar_string(
    tmp_path: Path, purpose: str
) -> None:
    board = _board(tmp_path / "board.yml")
    source = board.read_text(encoding="utf-8")
    board.write_text(
        source.replace(
            "purpose: 本人が安全に次の候補を選べるようにする",
            f"purpose: {purpose}",
        ),
        encoding="utf-8",
    )

    with pytest.raises(CurrentBoardError, match="purpose must be"):
        load_current_board(board)


@pytest.mark.parametrize(
    "children_yaml",
    [
        "children: not-a-list",
        "children:\n      - not-a-mapping",
        "children:\n      - title: []\n        detail: detail",
        "children:\n      - title: child\n        detail: {}",
        "children:\n      - title: ''\n        detail: detail",
        "children:\n      - title: child\n        detail: ''",
    ],
)
def test_malformed_completed_foundation_children_fail_closed(
    tmp_path: Path, children_yaml: str
) -> None:
    board = _board(tmp_path / "board.yml")
    source = board.read_text(encoding="utf-8")
    start = source.index("    children:\n", source.index("recently_done:"))
    end = source.index("parking_lot:", start)
    replacement = "    " + children_yaml.replace("\n", "\n    ") + "\n"
    board.write_text(source[:start] + replacement + source[end:], encoding="utf-8")

    with pytest.raises(CurrentBoardError, match="child|children"):
        load_current_board(board)


def test_publish_failure_preserves_previous_html(tmp_path: Path) -> None:
    board = _board(tmp_path / "board.yml", now="list")
    agent = _agent(tmp_path / "agent")
    reports = tmp_path / "reports"
    output = reports / "current" / "index.html"
    output.parent.mkdir(parents=True)
    output.write_text("previous", encoding="utf-8")

    with pytest.raises(CurrentBoardError):
        publish_current_board(board_path=board, agent_dir=agent, report_root=reports)

    assert output.read_text(encoding="utf-8") == "previous"


def test_json_like_public_file_blocks_publish(tmp_path: Path) -> None:
    board = _board(tmp_path / "board.yml")
    agent = _agent(tmp_path / "agent")
    reports = tmp_path / "reports"
    current = reports / "current"
    current.mkdir(parents=True)
    (current / "state.json").write_text("{}", encoding="utf-8")

    with pytest.raises(CurrentBoardError, match="JSON-like"):
        publish_current_board(board_path=board, agent_dir=agent, report_root=reports)


def test_board_source_symlink_is_rejected(tmp_path: Path) -> None:
    source = _board(tmp_path / "source.yml")
    link = tmp_path / "board.yml"
    link.symlink_to(source)
    with pytest.raises(CurrentBoardError, match="must not be a symlink"):
        load_current_board(link)
