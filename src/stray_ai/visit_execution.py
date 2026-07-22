from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .brain import CommandBrain
from .visitor import run_visit

_JST = ZoneInfo("Asia/Tokyo")
_REQUEST_SCHEMA = "stray-visit-request-v1"
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
_ALLOWED_BACKENDS = {"mock", "command"}


class VisitExecutionError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(_JST)


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisitExecutionError(f"{label} is not readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VisitExecutionError(f"{label} must contain a JSON object")
    return value


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _request_path(agent_dir: Path, request_file: Path) -> Path:
    request_root = (agent_dir / "visit_requests").resolve()
    resolved = request_file.resolve()
    try:
        resolved.relative_to(request_root)
    except ValueError as exc:
        raise VisitExecutionError("request must be inside the agent visit_requests directory") from exc
    if resolved.parent != request_root:
        raise VisitExecutionError("request must be a top-level visit_requests JSON file")
    if not resolved.is_file() or resolved.suffix.lower() != ".json":
        raise VisitExecutionError("request is not an existing JSON file")
    return resolved


def _profile_id(agent_dir: Path) -> str:
    profile_path = agent_dir / "profile.yml"
    if not profile_path.is_file():
        raise VisitExecutionError("agent profile.yml does not exist")
    try:
        loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VisitExecutionError(f"profile.yml is not readable: {exc}") from exc
    if not isinstance(loaded, dict):
        raise VisitExecutionError("profile.yml must contain a mapping")
    return str(loaded.get("id") or agent_dir.name)


def _require_resting(agent_dir: Path) -> None:
    state = _read_json_object(agent_dir / "state.json", label="state")
    if state.get("status") != "resting":
        raise VisitExecutionError("visitor must be resting")
    if state.get("current_location") is not None:
        raise VisitExecutionError("resting visitor must not have a current location")


def _relative_member(root: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise VisitExecutionError(f"{label} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute():
        raise VisitExecutionError(f"{label} must be relative to the snapshot root")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise VisitExecutionError(f"{label} escapes the snapshot root") from exc
    if not resolved.is_file():
        raise VisitExecutionError(f"{label} is not an existing file")
    if resolved.suffix.lower() not in _TEXT_SUFFIXES:
        raise VisitExecutionError(f"{label} is not a supported text page")
    return resolved


def _source_wake(agent_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    source = request.get("source_wake")
    if not isinstance(source, str) or not source.strip():
        raise VisitExecutionError("request has no source wake record")
    relative = Path(source)
    if relative.is_absolute():
        raise VisitExecutionError("source wake path must be relative")
    wake_root = (agent_dir / "wake_checks").resolve()
    wake_file = (agent_dir / relative).resolve()
    try:
        wake_file.relative_to(wake_root)
    except ValueError as exc:
        raise VisitExecutionError("source wake record escapes wake_checks") from exc
    if not wake_file.is_file():
        raise VisitExecutionError("source wake record does not exist")
    actual_sha = hashlib.sha256(wake_file.read_bytes()).hexdigest()
    if actual_sha != request.get("source_wake_sha256"):
        raise VisitExecutionError("source wake record changed after handoff preparation")

    wake = _read_json_object(wake_file, label="source wake record")
    if wake.get("eligible") is not True or wake.get("decision") != "request_visit":
        raise VisitExecutionError("source wake record no longer authorizes a visit request")
    brain = wake.get("brain")
    if not isinstance(brain, dict) or brain.get("status") not in {"accepted", "corrected"}:
        raise VisitExecutionError("source wake decision is not accepted")
    if wake.get("state_status_after") != "resting" or wake.get("current_location_after") is not None:
        raise VisitExecutionError("source wake record did not leave the visitor resting")
    wake_venue = wake.get("venue")
    if not isinstance(wake_venue, dict) or wake_venue.get("content_was_not_read") is not True:
        raise VisitExecutionError("source wake record lost the no-content-read boundary")
    return wake


def _validated_request(
    *,
    agent_dir: Path,
    request_file: Path,
    allowed_statuses: set[str],
) -> tuple[Path, dict[str, Any], Path, Path, list[Path]]:
    agent_dir = agent_dir.resolve()
    resolved_request = _request_path(agent_dir, request_file)
    request = _read_json_object(resolved_request, label="visit request")
    if request.get("schema") != _REQUEST_SCHEMA:
        raise VisitExecutionError("visit request schema is unsupported")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or request_id != resolved_request.stem:
        raise VisitExecutionError("request id does not match the request filename")
    if request.get("status") not in allowed_statuses:
        raise VisitExecutionError(
            f"visit request status must be one of {sorted(allowed_statuses)}"
        )
    profile_id = _profile_id(agent_dir)
    if request.get("agent_id") != profile_id:
        raise VisitExecutionError("visit request belongs to a different agent")

    constraints = request.get("constraints")
    if not isinstance(constraints, dict):
        raise VisitExecutionError("visit request has no constraints")
    if constraints.get("human_approval_required") is not True:
        raise VisitExecutionError("visit request does not require human approval")
    if constraints.get("automatic_execution_allowed") is not False:
        raise VisitExecutionError("visit request permits automatic execution")
    if constraints.get("venue_content_read") is not False:
        raise VisitExecutionError("visit request does not preserve the no-content-read boundary")
    if constraints.get("visit_started") is not False and request.get("status") != "executed":
        raise VisitExecutionError("visit request claims execution already started")

    wake = _source_wake(agent_dir, request)
    venue = request.get("venue")
    if not isinstance(venue, dict):
        raise VisitExecutionError("visit request has no venue")
    snapshot_id = venue.get("snapshot_id")
    snapshot_root = venue.get("snapshot_root")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise VisitExecutionError("visit request has no snapshot identity")
    if not isinstance(snapshot_root, str) or not snapshot_root.strip():
        raise VisitExecutionError("visit request has no snapshot root")
    root = Path(snapshot_root).resolve()
    if not root.is_dir() or root.name != snapshot_id:
        raise VisitExecutionError("snapshot root no longer matches the approved identity")
    wake_venue = wake.get("venue")
    if not isinstance(wake_venue, dict) or wake_venue.get("candidate_snapshot_id") != snapshot_id:
        raise VisitExecutionError("request snapshot no longer matches the wake candidate")

    entrance = _relative_member(root, venue.get("entrance"), label="entrance")
    arrival_value = venue.get("arrival_path", [])
    if not isinstance(arrival_value, list):
        raise VisitExecutionError("arrival path must be a list")
    arrival = [
        _relative_member(root, item, label=f"arrival path {index}")
        for index, item in enumerate(arrival_value, start=1)
    ]
    route = [entrance, *arrival]
    if len(set(route)) != len(route):
        raise VisitExecutionError("approved route contains duplicate pages")
    try:
        max_places = int(constraints.get("max_places"))
    except (TypeError, ValueError) as exc:
        raise VisitExecutionError("approved max_places is invalid") from exc
    if max_places < 1 or len(route) > max_places:
        raise VisitExecutionError("approved route exceeds max_places")
    return resolved_request, request, root, entrance, arrival


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _approval_payload(
    request: dict[str, Any],
    *,
    approved_by: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "request_core": {
            "schema": request.get("schema"),
            "request_id": request.get("request_id"),
            "agent_id": request.get("agent_id"),
            "source_wake": request.get("source_wake"),
            "source_wake_sha256": request.get("source_wake_sha256"),
            "venue": request.get("venue"),
            "constraints": request.get("constraints"),
        },
        "approved_by": approved_by,
        "plan": plan,
    }


def _approval_plan(
    *,
    backend: str,
    outbox: Path,
    seed: int | None,
    brain_command: list[str] | None,
    brain_label: str | None,
    brain_timeout: float,
) -> dict[str, Any]:
    if backend not in _ALLOWED_BACKENDS:
        raise VisitExecutionError("execution backend must be mock or command")
    resolved_outbox = outbox.resolve()
    if not resolved_outbox.is_dir():
        raise VisitExecutionError("approved outbox must be an existing directory")

    if backend == "mock":
        if brain_command or brain_label:
            raise VisitExecutionError("mock approval cannot include a brain command or label")
        return {
            "backend": "mock",
            "seed": int(seed) if seed is not None else None,
            "outbox": str(resolved_outbox),
        }

    command = [str(item) for item in brain_command or [] if str(item)]
    label = _clean_text(brain_label, 160)
    if not command:
        raise VisitExecutionError("command approval requires a brain command")
    if not label:
        raise VisitExecutionError("command approval requires a brain label")
    timeout = max(1.0, min(float(brain_timeout), 600.0))
    return {
        "backend": "command",
        "brain_command": command,
        "brain_label": label,
        "brain_timeout_seconds": timeout,
        "outbox": str(resolved_outbox),
    }


def approve_visit_request(
    *,
    agent_dir: Path,
    request_file: Path,
    confirm_request_id: str,
    approved_by: str,
    backend: str,
    outbox: Path,
    seed: int | None = None,
    brain_command: list[str] | None = None,
    brain_label: str | None = None,
    brain_timeout: float = 45.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    resolved, request, _, _, _ = _validated_request(
        agent_dir=agent_dir,
        request_file=request_file,
        allowed_statuses={"pending_human_approval", "approved"},
    )
    request_id = str(request["request_id"])
    if confirm_request_id != request_id:
        raise VisitExecutionError("exact request-id confirmation is required")
    approver = _clean_text(approved_by, 160)
    if not approver:
        raise VisitExecutionError("approved_by is required")
    _require_resting(agent_dir)
    plan = _approval_plan(
        backend=backend,
        outbox=outbox,
        seed=seed,
        brain_command=brain_command,
        brain_label=brain_label,
        brain_timeout=brain_timeout,
    )
    payload = _approval_payload(request, approved_by=approver, plan=plan)
    digest = _canonical_digest(payload)

    if request.get("status") == "approved":
        approval = request.get("approval")
        if not isinstance(approval, dict):
            raise VisitExecutionError("approved request has no approval record")
        if (
            approval.get("approved_by") != approver
            or approval.get("plan") != plan
            or approval.get("approval_digest") != digest
        ):
            raise VisitExecutionError("request is already approved with a different plan")
        return {"approved": False, "request_file": str(resolved), "request": request}

    approved_at = (now or _now()).isoformat(timespec="seconds")
    request["status"] = "approved"
    request["approval"] = {
        "approved_at": approved_at,
        "approved_by": approver,
        "confirmed_request_id": request_id,
        "plan": plan,
        "approval_digest": digest,
    }
    request["execution"] = {
        "claim_file": None,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "visit_file": None,
        "error": None,
    }
    _atomic_write_json(resolved, request)
    return {"approved": True, "request_file": str(resolved), "request": request}


def _approved_plan(request: dict[str, Any]) -> dict[str, Any]:
    approval = request.get("approval")
    if not isinstance(approval, dict):
        raise VisitExecutionError("approved request has no approval record")
    approved_by = approval.get("approved_by")
    plan = approval.get("plan")
    digest = approval.get("approval_digest")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise VisitExecutionError("approval has no approver")
    if not isinstance(plan, dict):
        raise VisitExecutionError("approval has no execution plan")
    expected = _canonical_digest(
        _approval_payload(request, approved_by=approved_by, plan=plan)
    )
    if digest != expected:
        raise VisitExecutionError("approval digest does not match the request and plan")

    backend = plan.get("backend")
    outbox = plan.get("outbox")
    if backend not in _ALLOWED_BACKENDS:
        raise VisitExecutionError("approved backend is unsupported")
    if not isinstance(outbox, str) or not Path(outbox).resolve().is_dir():
        raise VisitExecutionError("approved outbox no longer exists")
    if backend == "mock":
        if set(plan) != {"backend", "seed", "outbox"}:
            raise VisitExecutionError("mock execution plan contains unexpected fields")
        return plan

    command = plan.get("brain_command")
    label = plan.get("brain_label")
    timeout = plan.get("brain_timeout_seconds")
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) and item for item in command
    ):
        raise VisitExecutionError("approved brain command is invalid")
    if not isinstance(label, str) or not label.strip():
        raise VisitExecutionError("approved brain label is invalid")
    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise VisitExecutionError("approved brain timeout is invalid") from exc
    if not 1.0 <= timeout_value <= 600.0:
        raise VisitExecutionError("approved brain timeout is outside the allowed range")
    return plan


def _claim_execution(
    *,
    agent_dir: Path,
    request_file: Path,
    request: dict[str, Any],
    started_at: str,
) -> Path:
    claim_dir = agent_dir / "visit_requests" / "claims"
    claim_dir.mkdir(parents=True, exist_ok=True)
    claim_file = claim_dir / f"{request['request_id']}.json"
    claim = {
        "schema": "stray-visit-execution-claim-v1",
        "request_id": request["request_id"],
        "request_file": request_file.relative_to(agent_dir).as_posix(),
        "claimed_at": started_at,
        "automatic_retry_allowed": False,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(claim_file, flags, 0o600)
    except FileExistsError as exc:
        raise VisitExecutionError("visit execution was already claimed") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(claim, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # The durable claim intentionally remains after any post-claim failure.
        raise
    return claim_file


def execute_approved_visit(
    *,
    agent_dir: Path,
    request_file: Path,
    confirm_request_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    resolved, request, root, entrance, arrival = _validated_request(
        agent_dir=agent_dir,
        request_file=request_file,
        allowed_statuses={"approved"},
    )
    request_id = str(request["request_id"])
    if confirm_request_id != request_id:
        raise VisitExecutionError("exact request-id confirmation is required")
    _require_resting(agent_dir)
    plan = _approved_plan(request)
    started_at = (now or _now()).isoformat(timespec="seconds")
    claim_file = _claim_execution(
        agent_dir=agent_dir,
        request_file=resolved,
        request=request,
        started_at=started_at,
    )

    request["status"] = "executing"
    execution = request.get("execution") if isinstance(request.get("execution"), dict) else {}
    execution.update(
        {
            "claim_file": claim_file.relative_to(agent_dir).as_posix(),
            "started_at": started_at,
            "completed_at": None,
            "failed_at": None,
            "visit_file": None,
            "error": None,
        }
    )
    request["execution"] = execution
    _atomic_write_json(resolved, request)

    backend = str(plan["backend"])
    brain: CommandBrain | None = None
    seed: int | None = None
    if backend == "mock":
        seed_value = plan.get("seed")
        seed = int(seed_value) if seed_value is not None else None
    else:
        brain = CommandBrain(
            list(plan["brain_command"]),
            label=str(plan["brain_label"]),
            timeout_seconds=float(plan["brain_timeout_seconds"]),
        )

    try:
        visit = run_visit(
            agent_dir=agent_dir,
            local_root=root,
            entrance=entrance,
            arrival_path=arrival,
            outbox=Path(str(plan["outbox"])),
            seed=seed,
            brain=brain,
        )
    except Exception as exc:
        failed_at = _now().isoformat(timespec="seconds")
        request["status"] = "execution_failed"
        execution["failed_at"] = failed_at
        execution["error"] = _clean_text(f"{exc.__class__.__name__}: {exc}", 480)
        _atomic_write_json(resolved, request)
        raise VisitExecutionError(
            "approved Visit execution failed and is not eligible for automatic retry"
        ) from exc

    completed_at = _now().isoformat(timespec="seconds")
    request["status"] = "executed"
    constraints = request.get("constraints")
    if isinstance(constraints, dict):
        constraints["visit_started"] = True
    execution["completed_at"] = completed_at
    execution["visit_file"] = visit.get("visit_file")
    execution["exit_reason"] = visit.get("exit_reason")
    execution["backend"] = visit.get("backend")
    execution["brain_model"] = visit.get("brain_model")
    _atomic_write_json(resolved, request)
    return {
        "executed": True,
        "request_file": str(resolved),
        "claim_file": str(claim_file),
        "visit": visit,
        "request": request,
    }


def _approval_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-approve-visit")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--confirm-request-id", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--backend", choices=sorted(_ALLOWED_BACKENDS), required=True)
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--brain-command")
    parser.add_argument("--brain-label")
    parser.add_argument("--brain-timeout", type=float, default=45.0)
    return parser


def approval_main() -> None:
    parser = _approval_parser()
    args = parser.parse_args()
    command = shlex.split(args.brain_command) if args.brain_command else None
    try:
        result = approve_visit_request(
            agent_dir=args.agent,
            request_file=args.request,
            confirm_request_id=args.confirm_request_id,
            approved_by=args.approved_by,
            backend=args.backend,
            outbox=args.outbox,
            seed=args.seed,
            brain_command=command,
            brain_label=args.brain_label,
            brain_timeout=args.brain_timeout,
        )
    except VisitExecutionError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _execution_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-execute-approved-visit")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--confirm-request-id", required=True)
    return parser


def execution_main() -> None:
    parser = _execution_parser()
    args = parser.parse_args()
    try:
        result = execute_approved_visit(
            agent_dir=args.agent,
            request_file=args.request,
            confirm_request_id=args.confirm_request_id,
        )
    except VisitExecutionError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m stray_ai.visit_execution")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("approve", parents=[_approval_parser()], add_help=False)
    subparsers.add_parser("execute", parents=[_execution_parser()], add_help=False)
    args = parser.parse_args()

    if args.command == "approve":
        command = shlex.split(args.brain_command) if args.brain_command else None
        try:
            result = approve_visit_request(
                agent_dir=args.agent,
                request_file=args.request,
                confirm_request_id=args.confirm_request_id,
                approved_by=args.approved_by,
                backend=args.backend,
                outbox=args.outbox,
                seed=args.seed,
                brain_command=command,
                brain_label=args.brain_label,
                brain_timeout=args.brain_timeout,
            )
        except VisitExecutionError as exc:
            parser.error(str(exc))
    else:
        try:
            result = execute_approved_visit(
                agent_dir=args.agent,
                request_file=args.request,
                confirm_request_id=args.confirm_request_id,
            )
        except VisitExecutionError as exc:
            parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
