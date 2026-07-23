from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.current_board import CurrentBoardError, load_current_board, publish_current_board

_JST = ZoneInfo("Asia/Tokyo")


def _board(path: Path, *, now: str = "mapping") -> Path:
    now_block = (
        """
now:
  title: Multi-Venue Wake Selection v0
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
  - Venue-scoped wake comparison
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
    assert list((reports / "current").iterdir()) == [output]


def test_now_must_be_exactly_one_mapping(tmp_path: Path) -> None:
    board = _board(tmp_path / "board.yml", now="list")
    with pytest.raises(CurrentBoardError, match="exactly one NOW mapping"):
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
