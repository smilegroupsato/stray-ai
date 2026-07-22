from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import stray_ai.visit_execution as execution_module
from stray_ai.visit_execution import (
    VisitExecutionError,
    approve_visit_request,
    execute_approved_visit,
)
from stray_ai.visit_handoff import prepare_visit_request

_JST = ZoneInfo("Asia/Tokyo")
_APPROVED_AT = datetime(2026, 7, 22, 13, 0, tzinfo=_JST)
_EXECUTED_AT = datetime(2026, 7, 22, 13, 5, tzinfo=_JST)


def _prepared(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    agent = root / "agent"
    wake_dir = agent / "wake_checks"
    wake_dir.mkdir(parents=True)
    (agent / "profile.yml").write_text(
        """
id: test-stray
name: synthetic
attention:
  drawn_to: []
  tends_to_avoid: []
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
                "last_location": None,
                "fatigue": 0.0,
                "unresolved_impulses": ["Notice only the difference."],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (agent / "memory.md").write_text("# Memory\n", encoding="utf-8")

    wake = wake_dir / "2026-07-22_110000.json"
    wake.write_text(
        json.dumps(
            {
                "agent_id": "test-stray",
                "checked_at": "2026-07-22T11:00:00+09:00",
                "eligible": True,
                "venue": {
                    "previous_snapshot_id": "snap-a",
                    "candidate_snapshot_id": "snap-b",
                    "changed": True,
                    "content_was_not_read": True,
                },
                "brain": {
                    "status": "accepted",
                    "model": "test-wake-model",
                    "protocol": "stray-wake-v1",
                    "error": None,
                },
                "decision": "request_visit",
                "observation": "The opaque identity changed.",
                "reason": "A later bounded encounter may matter.",
                "impulses_added": ["Notice only the difference."],
                "state_status_after": "resting",
                "current_location_after": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = root / "snap-b"
    snapshot.mkdir()
    (snapshot / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (snapshot / "NEXT.md").write_text("# Next\n", encoding="utf-8")
    outbox = root / "outbox"
    outbox.mkdir()

    prepared = prepare_visit_request(
        agent_dir=agent,
        wake_file=wake,
        venue_id="test-venue",
        snapshot_root=snapshot,
        entrance=Path("README.md"),
        arrival_path=[Path("NEXT.md")],
        now=datetime(2026, 7, 22, 12, 0, tzinfo=_JST),
    )
    return agent, wake, snapshot, outbox, Path(prepared["request_file"])


def _request(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _approve_mock(
    *, agent: Path, request: Path, outbox: Path, seed: int = 7
) -> dict:
    return approve_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        approved_by="Taku Sato",
        backend="mock",
        outbox=outbox,
        seed=seed,
        now=_APPROVED_AT,
    )


def test_pending_request_cannot_execute(tmp_path: Path) -> None:
    agent, _, _, _, request = _prepared(tmp_path)

    with pytest.raises(VisitExecutionError, match="status must be"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )

    assert not (agent / "visit_requests" / "claims").exists()
    assert not (agent / "visits").exists()


def test_approval_is_explicit_idempotent_and_conflicts_fail_closed(tmp_path: Path) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)

    first = _approve_mock(agent=agent, request=request, outbox=outbox, seed=7)
    second = _approve_mock(agent=agent, request=request, outbox=outbox, seed=7)

    assert first["approved"] is True
    assert second["approved"] is False
    approved = _request(request)
    assert approved["status"] == "approved"
    assert approved["approval"]["approved_by"] == "Taku Sato"
    assert approved["approval"]["confirmed_request_id"] == request.stem
    assert approved["approval"]["plan"] == {
        "backend": "mock",
        "seed": 7,
        "outbox": str(outbox.resolve()),
    }
    assert len(approved["approval"]["approval_digest"]) == 64
    assert not (agent / "visits").exists()

    with pytest.raises(VisitExecutionError, match="different plan"):
        _approve_mock(agent=agent, request=request, outbox=outbox, seed=8)
    with pytest.raises(VisitExecutionError, match="exact request-id"):
        approve_visit_request(
            agent_dir=agent,
            request_file=request,
            confirm_request_id="wrong-id",
            approved_by="Taku Sato",
            backend="mock",
            outbox=outbox,
        )


def test_modified_wake_fails_before_approval(tmp_path: Path) -> None:
    agent, wake, _, outbox, request = _prepared(tmp_path)
    wake_record = _request(wake)
    wake_record["observation"] = "changed after preparation"
    wake.write_text(json.dumps(wake_record), encoding="utf-8")

    with pytest.raises(VisitExecutionError, match="changed after handoff"):
        _approve_mock(agent=agent, request=request, outbox=outbox)

    assert _request(request)["status"] == "pending_human_approval"


def test_mock_execution_runs_once_and_keeps_durable_claim(tmp_path: Path) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)
    _approve_mock(agent=agent, request=request, outbox=outbox)

    result = execute_approved_visit(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        now=_EXECUTED_AT,
    )

    assert result["executed"] is True
    assert result["visit"]["backend"] == "mock"
    visit_file = Path(result["visit"]["visit_file"])
    assert visit_file.is_file()
    assert len(list((agent / "visits").glob("*.json"))) == 1
    claim_file = Path(result["claim_file"])
    assert claim_file.is_file()

    completed = _request(request)
    assert completed["status"] == "executed"
    assert completed["constraints"]["visit_started"] is True
    assert completed["execution"]["visit_file"] == str(visit_file)
    state = _request(agent / "state.json")
    assert state["status"] == "resting"
    assert state["current_location"] is None
    assert state["visit_count"] == 5

    with pytest.raises(VisitExecutionError, match="status must be"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )

    # Even a manually reverted envelope cannot bypass the durable claim.
    completed["status"] = "approved"
    completed["constraints"]["visit_started"] = False
    request.write_text(json.dumps(completed, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(VisitExecutionError, match="already claimed"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )
    assert len(list((agent / "visits").glob("*.json"))) == 1


def test_command_brain_plan_is_fixed_at_approval_and_executes(tmp_path: Path) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)
    adapter = tmp_path / "brain.py"
    adapter.write_text(
        """
import json, sys
payload = json.load(sys.stdin)
assert payload["protocol"] == "stray-brain-v1"
print(json.dumps({
  "action": "leave_silently",
  "link_index": None,
  "observation": "A bounded synthetic visit occurred.",
  "memories": ["Synthetic command-brain memory."],
  "trace": None
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(adapter)]

    approved = approve_visit_request(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        approved_by="Taku Sato",
        backend="command",
        outbox=outbox,
        brain_command=command,
        brain_label="synthetic-brain",
        brain_timeout=5,
        now=_APPROVED_AT,
    )
    assert approved["request"]["approval"]["plan"]["brain_command"] == command

    result = execute_approved_visit(
        agent_dir=agent,
        request_file=request,
        confirm_request_id=request.stem,
        now=_EXECUTED_AT,
    )
    assert result["visit"]["backend"] == "command"
    assert result["visit"]["brain_model"] == "synthetic-brain"
    assert result["visit"]["memories_added"] == ["Synthetic command-brain memory."]


def test_tampered_request_core_or_approval_digest_fails_closed(tmp_path: Path) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)
    _approve_mock(agent=agent, request=request, outbox=outbox)
    approved = _request(request)
    approved["venue"]["arrival_path"] = []
    request.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(VisitExecutionError, match="approval digest"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )
    assert not (agent / "visit_requests" / "claims").exists()


def test_non_resting_state_fails_before_execution_claim(tmp_path: Path) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)
    _approve_mock(agent=agent, request=request, outbox=outbox)
    state = _request(agent / "state.json")
    state["status"] = "visiting"
    state["current_location"] = "/somewhere"
    (agent / "state.json").write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(VisitExecutionError, match="must be resting"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )
    assert not (agent / "visit_requests" / "claims").exists()


def test_post_claim_failure_is_fail_stop_and_not_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent, _, _, outbox, request = _prepared(tmp_path)
    _approve_mock(agent=agent, request=request, outbox=outbox)

    def fail_visit(**_: object) -> dict:
        raise RuntimeError("synthetic execution failure")

    monkeypatch.setattr(execution_module, "run_visit", fail_visit)
    with pytest.raises(VisitExecutionError, match="not eligible for automatic retry"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
            now=_EXECUTED_AT,
        )

    failed = _request(request)
    assert failed["status"] == "execution_failed"
    assert "synthetic execution failure" in failed["execution"]["error"]
    claim = agent / failed["execution"]["claim_file"]
    assert claim.is_file()

    failed["status"] = "approved"
    request.write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(VisitExecutionError, match="already claimed"):
        execute_approved_visit(
            agent_dir=agent,
            request_file=request,
            confirm_request_id=request.stem,
        )
