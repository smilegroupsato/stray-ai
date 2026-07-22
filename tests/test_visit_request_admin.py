from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.visit_execution import approve_visit_request
from stray_ai.visit_handoff import prepare_visit_request
from stray_ai.visit_request_admin import (
    VisitRequestAdminError,
    build_review_collection,
    cancel_visit_request,
    write_review_outputs,
)

_JST = ZoneInfo("Asia/Tokyo")
_CREATED = datetime(2026, 7, 22, 15, 0, tzinfo=_JST)
_APPROVED = datetime(2026, 7, 22, 15, 5, tzinfo=_JST)
_CANCELLED = datetime(2026, 7, 22, 15, 10, tzinfo=_JST)
_GENERATED = datetime(2026, 7, 22, 15, 15, tzinfo=_JST)


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


def _prepare(
    root: Path,
    agent: Path,
    *,
    stamp: str,
    snapshot_id: str,
    observation: str = "The opaque snapshot identity changed.",
) -> tuple[Path, Path]:
    wake = agent / "wake_checks" / f"{stamp}.json"
    wake.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "checked_at": "2026-07-22T15:00:00+09:00",
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
                "observation": observation,
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
        now=_CREATED,
    )
    return Path(prepared["request_file"]), wake


def _all_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_review_outputs_are_read_only_and_hide_local_execution_details(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    pending, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_150000",
        snapshot_id="snap-pending",
        observation="Looked at /srv/private/wake-state.json without reading content.",
    )
    approved, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_150100",
        snapshot_id="snap-approved",
    )
    outbox = tmp_path / "private-outbox"
    outbox.mkdir()
    secret_command = [
        "/usr/bin/python3",
        "/srv/private/brain_adapter.py",
        "--token=do-not-display",
    ]
    approve_visit_request(
        agent_dir=agent,
        request_file=approved,
        confirm_request_id=approved.stem,
        approved_by="Taku Sato",
        backend="command",
        outbox=outbox,
        brain_command=secret_command,
        brain_label="synthetic-brain",
        brain_timeout=10,
        now=_APPROVED,
    )
    before = _all_bytes(agent)
    html_output = tmp_path / "review" / "index.html"
    json_output = tmp_path / "review" / "requests.json"

    result = write_review_outputs(
        agent_dir=agent,
        html_output=html_output,
        json_output=json_output,
        generated_at=_GENERATED,
    )

    assert result["request_count"] == 2
    assert _all_bytes(agent) == before
    html_text = html_output.read_text(encoding="utf-8")
    json_text = json_output.read_text(encoding="utf-8")
    for forbidden in (
        str(tmp_path),
        str(outbox),
        "/srv/",
        "brain_adapter.py",
        "do-not-display",
    ):
        assert forbidden not in html_text
        assert forbidden not in json_text
    assert "<button" not in html_text
    assert "<form" not in html_text
    assert "読み取り専用" in html_text

    collection = json.loads(json_text)
    assert collection["boundaries"] == {
        "read_only": True,
        "venue_content_read": False,
        "contains_controls": False,
        "automatic_action_allowed": False,
    }
    by_status = {item["status"]: item for item in collection["requests"]}
    assert by_status["pending_human_approval"]["eligible_actions"] == ["approve", "cancel"]
    assert by_status["approved"]["eligible_actions"] == ["execute"]
    plan = by_status["approved"]["approval"]["plan"]
    assert plan["backend"] == "command"
    assert plan["brain_command_arg_count"] == 3
    assert len(plan["brain_command_sha256"]) == 64
    assert plan["outbox_configured"] is True
    assert pending.is_file()


def test_malformed_request_is_isolated_as_invalid_card(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_151000",
        snapshot_id="snap-valid",
    )
    malformed = agent / "visit_requests" / "broken.json"
    malformed.write_text("{not-json", encoding="utf-8")

    collection = build_review_collection(agent_dir=agent, generated_at=_GENERATED)

    assert collection["request_count"] == 2
    invalid = next(item for item in collection["requests"] if item["request_file"] == "broken.json")
    assert invalid["validity"] == "invalid"
    assert invalid["errors"] == ["request_json_invalid"]
    valid = next(item for item in collection["requests"] if item["request_file"] != "broken.json")
    assert valid["validity"] == "valid"
    assert valid["integrity"] == {
        "source_wake": "ok",
        "snapshot_identity": "ok",
        "route": "ok",
    }


def test_pending_cancellation_is_explicit_durable_and_idempotent(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    request, wake = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_152000",
        snapshot_id="snap-cancel",
    )
    protected_before = {
        path: path.read_bytes()
        for path in (agent / "profile.yml", agent / "state.json", agent / "memory.md", wake)
    }

    first = cancel_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        cancelled_by="Taku Sato",
        reason="This pending encounter is no longer needed.",
        now=_CANCELLED,
    )
    second = cancel_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        cancelled_by="Taku Sato",
        reason="This pending encounter is no longer needed.",
        now=_GENERATED,
    )

    assert first["cancelled"] is True
    assert second["cancelled"] is False
    cancelled = json.loads(request.read_text(encoding="utf-8"))
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation"] == {
        "cancelled_at": "2026-07-22T15:10:00+09:00",
        "cancelled_by": "Taku Sato",
        "confirmed_request_id": request.stem,
        "reason": "This pending encounter is no longer needed.",
    }
    assert not (agent / "visits").exists()
    assert not (agent / "visit_requests" / "claims").exists()
    for path, content in protected_before.items():
        assert path.read_bytes() == content

    summary = build_review_collection(agent_dir=agent, generated_at=_GENERATED)["requests"][0]
    assert summary["status"] == "cancelled"
    assert summary["eligible_actions"] == []
    assert summary["cancellation"]["cancelled_by"] == "Taku Sato"


def test_conflicting_repeated_cancellation_fails_closed(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    request, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_153000",
        snapshot_id="snap-conflict",
    )
    cancel_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        cancelled_by="Taku Sato",
        reason="Original reason.",
        now=_CANCELLED,
    )
    before = request.read_bytes()

    with pytest.raises(VisitRequestAdminError, match="different details"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
            cancelled_by="Another Person",
            reason="Different reason.",
        )
    assert request.read_bytes() == before


def test_non_pending_or_claimed_request_cannot_be_cancelled(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    approved, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_154000",
        snapshot_id="snap-approved-cancel",
    )
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    approve_visit_request(
        agent_dir=agent,
        request_file=approved,
        confirm_request_id=approved.stem,
        approved_by="Taku Sato",
        backend="mock",
        outbox=outbox,
        seed=7,
        now=_APPROVED,
    )
    approved_before = approved.read_bytes()
    with pytest.raises(VisitRequestAdminError, match="only pending_human_approval"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=approved,
            confirm_request_id=approved.stem,
            cancelled_by="Taku Sato",
            reason="Too late.",
        )
    assert approved.read_bytes() == approved_before

    pending, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_154100",
        snapshot_id="snap-claimed-cancel",
    )
    claim_dir = agent / "visit_requests" / "claims"
    claim_dir.mkdir()
    (claim_dir / f"{pending.stem}.json").write_text("{}\n", encoding="utf-8")
    pending_before = pending.read_bytes()
    with pytest.raises(VisitRequestAdminError, match="claimed"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=pending,
            confirm_request_id=pending.stem,
            cancelled_by="Taku Sato",
            reason="Claim exists.",
        )
    assert pending.read_bytes() == pending_before


def test_cancellation_requires_exact_id_actor_and_reason(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    request, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_155000",
        snapshot_id="snap-required",
    )
    before = request.read_bytes()

    with pytest.raises(VisitRequestAdminError, match="exact request-id"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=request,
            confirm_request_id="wrong",
            cancelled_by="Taku Sato",
            reason="Reason.",
        )
    with pytest.raises(VisitRequestAdminError, match="cancelled_by"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
            cancelled_by=" ",
            reason="Reason.",
        )
    with pytest.raises(VisitRequestAdminError, match="reason"):
        cancel_visit_request(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
            cancelled_by="Taku Sato",
            reason=" ",
        )
    assert request.read_bytes() == before


def test_review_command_fingerprint_matches_approved_command(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    request, _ = _prepare(
        tmp_path,
        agent,
        stamp="2026-07-22_160000",
        snapshot_id="snap-fingerprint",
    )
    outbox = tmp_path / "outbox-fingerprint"
    outbox.mkdir()
    command = ["python", "adapter.py", "--mode", "bounded"]
    approve_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        approved_by="Taku Sato",
        backend="command",
        outbox=outbox,
        brain_command=command,
        brain_label="fingerprint-brain",
        now=_APPROVED,
    )

    summary = build_review_collection(agent_dir=agent, generated_at=_GENERATED)["requests"][0]
    expected = hashlib.sha256(
        json.dumps(
            {"brain_command": command},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert summary["approval"]["plan"]["brain_command_sha256"] == expected
    assert summary["approval"]["approval_digest_status"] == "ok"
