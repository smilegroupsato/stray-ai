from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

_JST = ZoneInfo("Asia/Tokyo")
_REQUEST_SCHEMA = "stray-visit-request-v1"
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
_KNOWN_STATUSES = {
    "pending_human_approval",
    "approved",
    "executing",
    "executed",
    "execution_failed",
    "cancelled",
}
_ABSOLUTE_PATH = re.compile(r"(?<![\w.])/(?:[^\s<>\"']+/)+[^\s<>\"']*")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\(?:[^\s<>\"']+\\)*[^\s<>\"']*")


class VisitRequestAdminError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(_JST)


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _public_text(value: Any, limit: int) -> str:
    text = _clean_text(value, limit)
    text = _ABSOLUTE_PATH.sub("[local path hidden]", text)
    return _WINDOWS_PATH.sub("[local path hidden]", text)


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisitRequestAdminError(f"{label} is not readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VisitRequestAdminError(f"{label} must contain a JSON object")
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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _profile_id(agent_dir: Path) -> str:
    profile_path = agent_dir / "profile.yml"
    if not profile_path.is_file():
        raise VisitRequestAdminError("agent profile.yml does not exist")
    try:
        loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VisitRequestAdminError(f"profile.yml is not readable: {exc}") from exc
    if not isinstance(loaded, dict):
        raise VisitRequestAdminError("profile.yml must contain a mapping")
    return str(loaded.get("id") or agent_dir.name)


def _request_path(agent_dir: Path, request_file: Path) -> Path:
    request_root = (agent_dir / "visit_requests").resolve()
    resolved = request_file.resolve()
    try:
        resolved.relative_to(request_root)
    except ValueError as exc:
        raise VisitRequestAdminError("request must be inside the agent visit_requests directory") from exc
    if resolved.parent != request_root:
        raise VisitRequestAdminError("request must be a top-level visit_requests JSON file")
    if not resolved.is_file() or resolved.suffix.lower() != ".json":
        raise VisitRequestAdminError("request is not an existing JSON file")
    return resolved


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


def _relative_display_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix()


def _source_wake_status(agent_dir: Path, request: dict[str, Any]) -> str:
    source = _relative_display_path(request.get("source_wake"))
    if source is None:
        return "invalid"
    wake_root = (agent_dir / "wake_checks").resolve()
    wake_file = (agent_dir / source).resolve()
    try:
        wake_file.relative_to(wake_root)
    except ValueError:
        return "invalid"
    if not wake_file.is_file():
        return "missing"
    expected = request.get("source_wake_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return "invalid"
    actual = hashlib.sha256(wake_file.read_bytes()).hexdigest()
    return "ok" if actual == expected else "changed"


def _venue_integrity(request: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    venue = request.get("venue")
    if not isinstance(venue, dict):
        return {
            "venue_id": None,
            "snapshot_id": None,
            "entrance": None,
            "arrival_path": [],
        }, "invalid", "invalid"

    venue_id = _public_text(venue.get("venue_id"), 120) or None
    snapshot_id = _public_text(venue.get("snapshot_id"), 160) or None
    entrance = _relative_display_path(venue.get("entrance"))
    raw_arrival = venue.get("arrival_path", [])
    if not isinstance(raw_arrival, list):
        raw_arrival = []
    arrival = [_relative_display_path(item) for item in raw_arrival]
    safe_arrival = [item for item in arrival if item is not None]
    public = {
        "venue_id": venue_id,
        "snapshot_id": snapshot_id,
        "entrance": entrance,
        "arrival_path": safe_arrival,
    }

    snapshot_root = venue.get("snapshot_root")
    if not isinstance(snapshot_root, str) or not snapshot_root.strip() or snapshot_id is None:
        return public, "invalid", "invalid"
    root = Path(snapshot_root).resolve()
    if not root.is_dir():
        return public, "missing", "missing"
    snapshot_status = "ok" if root.name == snapshot_id else "mismatch"

    route_values = [venue.get("entrance"), *raw_arrival]
    if entrance is None or len(safe_arrival) != len(raw_arrival):
        return public, snapshot_status, "invalid"
    route: list[Path] = []
    for index, value in enumerate(route_values, start=1):
        relative = Path(str(value))
        if relative.is_absolute():
            return public, snapshot_status, "invalid"
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return public, snapshot_status, "outside"
        if not resolved.is_file():
            return public, snapshot_status, "missing"
        if resolved.suffix.lower() not in _TEXT_SUFFIXES:
            return public, snapshot_status, "invalid"
        route.append(resolved)
    if len(set(route)) != len(route):
        return public, snapshot_status, "duplicate"
    return public, snapshot_status, "ok"


def _safe_plan_summary(plan: Any) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    backend = plan.get("backend")
    if backend == "mock":
        return {
            "backend": "mock",
            "seed": plan.get("seed") if isinstance(plan.get("seed"), int) else None,
            "outbox_configured": isinstance(plan.get("outbox"), str),
        }
    if backend == "command":
        command = plan.get("brain_command")
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            command = []
        fingerprint = _canonical_digest({"brain_command": command}) if command else None
        timeout = plan.get("brain_timeout_seconds")
        return {
            "backend": "command",
            "brain_label": _public_text(plan.get("brain_label"), 160) or None,
            "brain_timeout_seconds": timeout if isinstance(timeout, (int, float)) else None,
            "brain_command_arg_count": len(command),
            "brain_command_sha256": fingerprint,
            "outbox_configured": isinstance(plan.get("outbox"), str),
        }
    return {"backend": _public_text(backend, 40) or "invalid"}


def _approval_summary(request: dict[str, Any]) -> dict[str, Any] | None:
    approval = request.get("approval")
    if not isinstance(approval, dict):
        return None
    approved_by = _public_text(approval.get("approved_by"), 160) or None
    plan = approval.get("plan")
    digest_status = "not_applicable"
    digest = approval.get("approval_digest")
    if approved_by and isinstance(plan, dict):
        expected = _canonical_digest(
            _approval_payload(request, approved_by=str(approval.get("approved_by")), plan=plan)
        )
        digest_status = "ok" if digest == expected else "mismatch"
    return {
        "approved_at": _public_text(approval.get("approved_at"), 80) or None,
        "approved_by": approved_by,
        "confirmed_request_id": _public_text(approval.get("confirmed_request_id"), 180) or None,
        "plan": _safe_plan_summary(plan),
        "approval_digest_status": digest_status,
    }


def _cancellation_summary(request: dict[str, Any]) -> dict[str, Any] | None:
    cancellation = request.get("cancellation")
    if not isinstance(cancellation, dict):
        return None
    return {
        "cancelled_at": _public_text(cancellation.get("cancelled_at"), 80) or None,
        "cancelled_by": _public_text(cancellation.get("cancelled_by"), 160) or None,
        "confirmed_request_id": _public_text(
            cancellation.get("confirmed_request_id"), 180
        ) or None,
        "reason": _public_text(cancellation.get("reason"), 360) or None,
    }


def _execution_summary(request: dict[str, Any]) -> dict[str, Any] | None:
    execution = request.get("execution")
    if not isinstance(execution, dict):
        return None
    visit_file = execution.get("visit_file")
    visit_name = Path(visit_file).name if isinstance(visit_file, str) and visit_file else None
    claim_file = _relative_display_path(execution.get("claim_file"))
    return {
        "claim_file": claim_file,
        "started_at": _public_text(execution.get("started_at"), 80) or None,
        "completed_at": _public_text(execution.get("completed_at"), 80) or None,
        "failed_at": _public_text(execution.get("failed_at"), 80) or None,
        "visit_file": visit_name,
        "exit_reason": _public_text(execution.get("exit_reason"), 120) or None,
        "backend": _public_text(execution.get("backend"), 40) or None,
        "brain_model": _public_text(execution.get("brain_model"), 160) or None,
        "error": _public_text(execution.get("error"), 360) or None,
    }


def _eligible_actions(status: str | None) -> list[str]:
    if status == "pending_human_approval":
        return ["approve", "cancel"]
    if status == "approved":
        return ["execute"]
    return []


def summarize_request(agent_dir: Path, request_file: Path) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    summary: dict[str, Any] = {
        "request_file": request_file.name,
        "validity": "invalid",
        "errors": [],
        "eligible_actions": [],
    }
    try:
        request = _read_json_object(request_file, label="visit request")
    except VisitRequestAdminError:
        summary["errors"] = ["request_json_invalid"]
        return summary

    errors: list[str] = []
    request_id = request.get("request_id")
    status = request.get("status")
    profile_id = _profile_id(agent_dir)
    if request.get("schema") != _REQUEST_SCHEMA:
        errors.append("unsupported_schema")
    if not isinstance(request_id, str) or request_id != request_file.stem:
        errors.append("request_id_mismatch")
    if request.get("agent_id") != profile_id:
        errors.append("agent_id_mismatch")
    if status not in _KNOWN_STATUSES:
        errors.append("unknown_status")

    venue, snapshot_status, route_status = _venue_integrity(request)
    source_wake = _relative_display_path(request.get("source_wake"))
    wake = request.get("wake") if isinstance(request.get("wake"), dict) else {}
    constraints = request.get("constraints") if isinstance(request.get("constraints"), dict) else {}
    summary.update(
        {
            "request_id": _public_text(request_id, 180) or None,
            "status": status if isinstance(status, str) else None,
            "created_at": _public_text(request.get("created_at"), 80) or None,
            "agent_id": _public_text(request.get("agent_id"), 120) or None,
            "source_wake": source_wake,
            "wake": {
                "checked_at": _public_text(wake.get("checked_at"), 80) or None,
                "decision": _public_text(wake.get("decision"), 80) or None,
                "observation": _public_text(wake.get("observation"), 480) or None,
                "reason": _public_text(wake.get("reason"), 480) or None,
                "impulses_added": [
                    _public_text(item, 240)
                    for item in wake.get("impulses_added", [])
                    if _public_text(item, 240)
                ]
                if isinstance(wake.get("impulses_added", []), list)
                else [],
            },
            "venue": venue,
            "constraints": {
                "max_places": constraints.get("max_places")
                if isinstance(constraints.get("max_places"), int)
                else None,
                "human_approval_required": constraints.get("human_approval_required") is True,
                "automatic_execution_allowed": constraints.get("automatic_execution_allowed")
                is True,
                "venue_content_read": constraints.get("venue_content_read") is True,
                "visit_started": constraints.get("visit_started") is True,
            },
            "integrity": {
                "source_wake": _source_wake_status(agent_dir, request),
                "snapshot_identity": snapshot_status,
                "route": route_status,
            },
            "approval": _approval_summary(request),
            "cancellation": _cancellation_summary(request),
            "execution": _execution_summary(request),
            "eligible_actions": _eligible_actions(status if isinstance(status, str) else None),
            "errors": errors,
            "validity": "valid" if not errors else "invalid",
        }
    )
    return summary


def build_review_collection(
    *,
    agent_dir: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    profile_id = _profile_id(agent_dir)
    request_dir = agent_dir / "visit_requests"
    requests = [
        summarize_request(agent_dir, path)
        for path in sorted(request_dir.glob("*.json"))
        if path.is_file()
    ] if request_dir.is_dir() else []
    counts: dict[str, int] = {}
    for request in requests:
        status = str(request.get("status") or "invalid")
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema": "stray-visit-request-review-v1",
        "generated_at": (generated_at or _now()).isoformat(timespec="seconds"),
        "agent_id": profile_id,
        "request_count": len(requests),
        "status_counts": counts,
        "requests": requests,
        "boundaries": {
            "read_only": True,
            "venue_content_read": False,
            "contains_controls": False,
            "automatic_action_allowed": False,
        },
    }


def _html_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def render_review_html(collection: dict[str, Any]) -> str:
    cards: list[str] = []
    for request in collection.get("requests", []):
        wake = request.get("wake") if isinstance(request.get("wake"), dict) else {}
        venue = request.get("venue") if isinstance(request.get("venue"), dict) else {}
        integrity = request.get("integrity") if isinstance(request.get("integrity"), dict) else {}
        route = [venue.get("entrance"), *venue.get("arrival_path", [])]
        route_html = "".join(f"<li>{_html_value(item)}</li>" for item in route if item)
        actions = request.get("eligible_actions", [])
        actions_text = ", ".join(str(item) for item in actions) if actions else "none"
        impulses = wake.get("impulses_added", []) if isinstance(wake.get("impulses_added"), list) else []
        impulses_html = "".join(f"<li>{_html_value(item)}</li>" for item in impulses)
        approval = request.get("approval") if isinstance(request.get("approval"), dict) else None
        cancellation = request.get("cancellation") if isinstance(request.get("cancellation"), dict) else None
        plan = approval.get("plan") if approval and isinstance(approval.get("plan"), dict) else None
        plan_html = ""
        if plan:
            plan_rows = "".join(
                f"<dt>{_html_value(key)}</dt><dd>{_html_value(value)}</dd>"
                for key, value in plan.items()
            )
            plan_html = f"<h4>承認済み実行計画（秘匿済み）</h4><dl>{plan_rows}</dl>"
        cancellation_html = ""
        if cancellation:
            cancellation_html = (
                "<h4>取消記録</h4><dl>"
                f"<dt>取消日時</dt><dd>{_html_value(cancellation.get('cancelled_at'))}</dd>"
                f"<dt>取消者</dt><dd>{_html_value(cancellation.get('cancelled_by'))}</dd>"
                f"<dt>理由</dt><dd>{_html_value(cancellation.get('reason'))}</dd>"
                "</dl>"
            )
        errors = request.get("errors", [])
        error_html = ""
        if errors:
            error_html = "<p class=\"error\">" + _html_value(", ".join(errors)) + "</p>"
        cards.append(
            "<article class=\"request-card\">"
            f"<header><span class=\"status\">{_html_value(request.get('status'))}</span>"
            f"<h2>{_html_value(request.get('request_id') or request.get('request_file'))}</h2></header>"
            f"{error_html}"
            "<dl class=\"summary\">"
            f"<dt>作成日時</dt><dd>{_html_value(request.get('created_at'))}</dd>"
            f"<dt>Venue</dt><dd>{_html_value(venue.get('venue_id'))}</dd>"
            f"<dt>Snapshot</dt><dd>{_html_value(venue.get('snapshot_id'))}</dd>"
            f"<dt>次に可能な人間操作</dt><dd>{_html_value(actions_text)}</dd>"
            "</dl>"
            "<h3>Wake判断</h3><dl>"
            f"<dt>確認日時</dt><dd>{_html_value(wake.get('checked_at'))}</dd>"
            f"<dt>観察</dt><dd>{_html_value(wake.get('observation'))}</dd>"
            f"<dt>理由</dt><dd>{_html_value(wake.get('reason'))}</dd>"
            "</dl>"
            f"<ul>{impulses_html}</ul>"
            "<h3>承認された経路</h3>"
            f"<ol>{route_html}</ol>"
            "<h3>整合性</h3><dl>"
            f"<dt>Wake記録</dt><dd>{_html_value(integrity.get('source_wake'))}</dd>"
            f"<dt>Snapshot identity</dt><dd>{_html_value(integrity.get('snapshot_identity'))}</dd>"
            f"<dt>Route</dt><dd>{_html_value(integrity.get('route'))}</dd>"
            "</dl>"
            f"{plan_html}{cancellation_html}"
            "</article>"
        )
    empty = "<p class=\"empty\">Visit Requestはありません。</p>" if not cards else ""
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stray AI Visit Request Review</title>
<style>
:root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { max-width: 960px; margin: 0 auto; padding: 1.5rem; line-height: 1.6; }
header.page { margin-bottom: 2rem; }
.notice { border: 1px solid currentColor; border-radius: .75rem; padding: 1rem; }
.request-card { border: 1px solid color-mix(in srgb, currentColor 35%, transparent); border-radius: 1rem; padding: 1.25rem; margin: 1.25rem 0; overflow-wrap: anywhere; }
.request-card header { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; }
.request-card h2 { font-size: 1.1rem; margin: 0; }
.status { font-weight: 700; border: 1px solid currentColor; border-radius: 999px; padding: .15rem .6rem; }
dl { display: grid; grid-template-columns: minmax(10rem, 14rem) 1fr; gap: .35rem .9rem; }
dt { font-weight: 700; }
dd { margin: 0; }
.error { font-weight: 700; }
@media (max-width: 640px) { body { padding: 1rem; } dl { grid-template-columns: 1fr; } dt { margin-top: .5rem; } }
</style>
</head>
<body>
<header class="page">
<p>STRAY AI / LOCAL REVIEW</p>
<h1>Visit Request Review</h1>
<p class="notice">このページは読み取り専用です。承認・取消・Visit実行を行う操作部品はありません。Venue本文は読み込まず、local absolute pathとbrain command全文は表示しません。</p>
<dl>
<dt>Agent</dt><dd>""" + _html_value(collection.get("agent_id")) + """</dd>
<dt>生成日時</dt><dd>""" + _html_value(collection.get("generated_at")) + """</dd>
<dt>Request数</dt><dd>""" + _html_value(collection.get("request_count")) + """</dd>
</dl>
</header>
<main>""" + empty + "".join(cards) + """</main>
</body>
</html>
"""


def write_review_outputs(
    *,
    agent_dir: Path,
    html_output: Path,
    json_output: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    collection = build_review_collection(agent_dir=agent_dir, generated_at=generated_at)
    _atomic_write_text(html_output.resolve(), render_review_html(collection))
    _atomic_write_json(json_output.resolve(), collection)
    return {
        "generated": True,
        "html_output": str(html_output.resolve()),
        "json_output": str(json_output.resolve()),
        "request_count": collection["request_count"],
        "status_counts": collection["status_counts"],
    }


def cancel_visit_request(
    *,
    agent_dir: Path,
    request_file: Path,
    confirm_request_id: str,
    cancelled_by: str,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_dir = agent_dir.resolve()
    resolved = _request_path(agent_dir, request_file)
    request = _read_json_object(resolved, label="visit request")
    if request.get("schema") != _REQUEST_SCHEMA:
        raise VisitRequestAdminError("visit request schema is unsupported")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or request_id != resolved.stem:
        raise VisitRequestAdminError("request id does not match the request filename")
    if confirm_request_id != request_id:
        raise VisitRequestAdminError("exact request-id confirmation is required")
    if request.get("agent_id") != _profile_id(agent_dir):
        raise VisitRequestAdminError("visit request belongs to a different agent")

    actor = _clean_text(cancelled_by, 160)
    cancellation_reason = _clean_text(reason, 360)
    if not actor:
        raise VisitRequestAdminError("cancelled_by is required")
    if not cancellation_reason:
        raise VisitRequestAdminError("cancellation reason is required")

    status = request.get("status")
    if status == "cancelled":
        cancellation = request.get("cancellation")
        if not isinstance(cancellation, dict):
            raise VisitRequestAdminError("cancelled request has no cancellation record")
        if (
            cancellation.get("cancelled_by") != actor
            or cancellation.get("reason") != cancellation_reason
            or cancellation.get("confirmed_request_id") != request_id
        ):
            raise VisitRequestAdminError("request is already cancelled with different details")
        return {"cancelled": False, "request_file": str(resolved), "request": request}
    if status != "pending_human_approval":
        raise VisitRequestAdminError("only pending_human_approval requests can be cancelled")

    claim_file = agent_dir / "visit_requests" / "claims" / f"{request_id}.json"
    if claim_file.exists():
        raise VisitRequestAdminError("claimed Visit Request cannot be cancelled")
    constraints = request.get("constraints")
    if not isinstance(constraints, dict) or constraints.get("visit_started") is not False:
        raise VisitRequestAdminError("Visit Request is not safely cancellable")
    approval = request.get("approval")
    if isinstance(approval, dict) and (
        approval.get("approved_at") is not None or approval.get("approved_by") is not None
    ):
        raise VisitRequestAdminError("approved Visit Request cannot be cancelled")
    execution = request.get("execution")
    if isinstance(execution, dict) and any(
        execution.get(key) is not None
        for key in ("claim_file", "started_at", "completed_at", "failed_at", "visit_file")
    ):
        raise VisitRequestAdminError("Visit Request with execution history cannot be cancelled")

    request["status"] = "cancelled"
    request["cancellation"] = {
        "cancelled_at": (now or _now()).isoformat(timespec="seconds"),
        "cancelled_by": actor,
        "confirmed_request_id": request_id,
        "reason": cancellation_reason,
    }
    _atomic_write_json(resolved, request)
    return {"cancelled": True, "request_file": str(resolved), "request": request}


def _review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-review-visit-requests")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser


def review_main() -> None:
    parser = _review_parser()
    args = parser.parse_args()
    try:
        result = write_review_outputs(
            agent_dir=args.agent,
            html_output=args.html_output,
            json_output=args.json_output,
        )
    except VisitRequestAdminError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _cancel_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-cancel-visit-request")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--confirm-request-id", required=True)
    parser.add_argument("--cancelled-by", required=True)
    parser.add_argument("--reason", required=True)
    return parser


def cancel_main() -> None:
    parser = _cancel_parser()
    args = parser.parse_args()
    try:
        result = cancel_visit_request(
            agent_dir=args.agent,
            request_file=args.request,
            confirm_request_id=args.confirm_request_id,
            cancelled_by=args.cancelled_by,
            reason=args.reason,
        )
    except VisitRequestAdminError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m stray_ai.visit_request_admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("review", parents=[_review_parser()], add_help=False)
    subparsers.add_parser("cancel", parents=[_cancel_parser()], add_help=False)
    args = parser.parse_args()
    if args.command == "review":
        try:
            result = write_review_outputs(
                agent_dir=args.agent,
                html_output=args.html_output,
                json_output=args.json_output,
            )
        except VisitRequestAdminError as exc:
            parser.error(str(exc))
    else:
        try:
            result = cancel_visit_request(
                agent_dir=args.agent,
                request_file=args.request,
                confirm_request_id=args.confirm_request_id,
                cancelled_by=args.cancelled_by,
                reason=args.reason,
            )
        except VisitRequestAdminError as exc:
            parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
