from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import stray_ai.gateway_request_review as gateway_module
from stray_ai.gateway_request_review import (
    GatewayRequestReviewError,
    publish_gateway_request_review,
)
from stray_ai.visit_handoff import prepare_visit_request
from stray_ai.visit_request_admin import cancel_visit_request

_JST = ZoneInfo("Asia/Tokyo")
_NOW = datetime(2026, 7, 22, 18, 0, tzinfo=_JST)


def _agent(root: Path) -> Path:
    agent = root / "agent"
    (agent / "wake_checks").mkdir(parents=True)
    (agent / "profile.yml").write_text(
        """
id: test-stray
name: synthetic
movement:
  max_places_per_visit: 3
  may_leave_silently: true
memory:
  max_new_memories_per_visit: 2
trace:
  max_characters: 120
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "visit_count": 4,
                "current_location": None,
                "fatigue": 0.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")
    return agent


def _request(root: Path, agent: Path, *, stamp: str, snapshot_id: str) -> Path:
    wake = agent / "wake_checks" / f"{stamp}.json"
    wake.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "checked_at": "2026-07-22T17:00:00+09:00",
                "eligible": True,
                "venue": {
                    "previous_snapshot_id": "previous",
                    "candidate_snapshot_id": snapshot_id,
                    "changed": True,
                    "content_was_not_read": True,
                },
                "brain": {
                    "status": "accepted",
                    "model": "synthetic-wake",
                    "protocol": "stray-wake-v1",
                    "error": None,
                },
                "decision": "request_visit",
                "observation": "A private /srv/secret/source changed opaquely.",
                "reason": "A later bounded encounter may matter.",
                "impulses_added": ["Notice only the difference."],
                "state_status_after": "resting",
                "current_location_after": None,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot = root / snapshot_id
    snapshot.mkdir()
    (snapshot / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (snapshot / "NEXT.md").write_text("# Next\n", encoding="utf-8")
    prepared = prepare_visit_request(
        agent_dir=agent,
        wake_file=wake,
        venue_id=f"venue-{snapshot_id}",
        snapshot_root=snapshot,
        entrance=Path("README.md"),
        arrival_path=[Path("NEXT.md")],
        now=_NOW,
    )
    return Path(prepared["request_file"])


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_empty_review_publishes_one_html_only_and_keeps_agent_unchanged(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    report_root = tmp_path / "reports"
    report_root.mkdir()
    before = _bytes(agent)

    result = publish_gateway_request_review(
        agent_dir=agent,
        report_root=report_root,
        generated_at=_NOW,
    )

    output = report_root / "request-review" / "index.html"
    assert result["request_count"] == 0
    assert result["gateway_path"] == "/stray-ai/request-review/index.html"
    assert output.is_file()
    assert list((report_root / "request-review").iterdir()) == [output]
    assert not list(report_root.rglob("*.json*"))
    assert _bytes(agent) == before


def test_pending_cancelled_and_malformed_requests_render_safely(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    pending = _request(tmp_path, agent, stamp="2026-07-22_170000", snapshot_id="snap-a")
    cancelled = _request(tmp_path, agent, stamp="2026-07-22_170100", snapshot_id="snap-b")
    cancel_visit_request(
        agent_dir=agent,
        request_file=cancelled,
        confirm_request_id=cancelled.stem,
        cancelled_by="Taku Sato",
        reason="Synthetic cancellation.",
        now=_NOW,
    )
    (agent / "visit_requests" / "broken.json").write_text("{not-json", encoding="utf-8")
    report_root = tmp_path / "reports"
    report_root.mkdir()
    before = _bytes(agent)

    result = publish_gateway_request_review(
        agent_dir=agent,
        report_root=report_root,
        generated_at=_NOW,
    )

    html = (report_root / "request-review" / "index.html").read_text(encoding="utf-8")
    assert result["request_count"] == 3
    assert pending.stem in html
    assert cancelled.stem in html
    assert "cancelled" in html
    assert "invalid" in html
    assert "[local path hidden]" in html
    for forbidden in ("/srv/", "snapshot_root", "brain_command", "<button", "<form"):
        assert forbidden not in html
    assert _bytes(agent) == before


def test_existing_json_blocks_publish_before_old_page_changes(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    report_root = tmp_path / "reports"
    review_dir = report_root / "request-review"
    review_dir.mkdir(parents=True)
    output = review_dir / "index.html"
    output.write_text("old page", encoding="utf-8")
    (review_dir / "requests.json").write_text("{}", encoding="utf-8")

    with pytest.raises(GatewayRequestReviewError, match="JSON-like"):
        publish_gateway_request_review(agent_dir=agent, report_root=report_root)

    assert output.read_text(encoding="utf-8") == "old page"


def test_unsafe_render_fails_before_old_page_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = _agent(tmp_path)
    report_root = tmp_path / "reports"
    output = report_root / "request-review" / "index.html"
    output.parent.mkdir(parents=True)
    output.write_text("old page", encoding="utf-8")
    monkeypatch.setattr(
        gateway_module,
        "render_review_html",
        lambda _: "<html><form><button>unsafe</button></form></html>",
    )

    with pytest.raises(GatewayRequestReviewError, match="safety check"):
        publish_gateway_request_review(agent_dir=agent, report_root=report_root)

    assert output.read_text(encoding="utf-8") == "old page"


def test_missing_report_root_and_symlink_targets_fail_closed(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(GatewayRequestReviewError, match="existing directory"):
        publish_gateway_request_review(agent_dir=agent, report_root=tmp_path / "missing")

    report_root = tmp_path / "reports"
    outside = tmp_path / "outside"
    report_root.mkdir()
    outside.mkdir()
    (report_root / "request-review").symlink_to(outside, target_is_directory=True)
    with pytest.raises(GatewayRequestReviewError, match="must not be a symlink"):
        publish_gateway_request_review(agent_dir=agent, report_root=report_root)
    assert not (outside / "index.html").exists()


def test_symlink_index_is_rejected_without_touching_target(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    report_root = tmp_path / "reports"
    review_dir = report_root / "request-review"
    review_dir.mkdir(parents=True)
    target = tmp_path / "outside.html"
    target.write_text("outside", encoding="utf-8")
    (review_dir / "index.html").symlink_to(target)

    with pytest.raises(GatewayRequestReviewError, match="index must not be a symlink"):
        publish_gateway_request_review(agent_dir=agent, report_root=report_root)

    assert target.read_text(encoding="utf-8") == "outside"
