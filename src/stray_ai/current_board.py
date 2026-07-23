from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .brand import cyberpunk_css, favicon_link_html, inline_title_mark_svg

_JST = ZoneInfo("Asia/Tokyo")
_PUBLISHED_RELATIVE_PATH = Path("current/index.html")
_FORBIDDEN_HTML_MARKERS = (
    "/srv/",
    "snapshot_root",
    "brain_command",
    "<button",
    "<form",
    "<script",
    "javascript:",
    "file://",
)
_SECTION_KEYS = ("next", "hold", "recently_done", "parking_lot", "not_doing")


class CurrentBoardError(RuntimeError):
    pass


def _clean_text(value: Any, *, limit: int = 360) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.split())[:limit]


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _normalize_item(value: Any, *, section: str) -> dict[str, Any]:
    if isinstance(value, str):
        title = _clean_text(value)
        if not title:
            raise CurrentBoardError(f"{section} contains an empty item")
        return {"title": title, "detail": "", "items": [], "children": []}
    if not isinstance(value, dict):
        raise CurrentBoardError(f"{section} items must be strings or mappings")
    title = _clean_text(value.get("title"))
    if not title:
        raise CurrentBoardError(f"{section} item title is required")
    detail = _clean_text(value.get("detail"))
    nested = value.get("items", [])
    if nested is None:
        nested = []
    if not isinstance(nested, list):
        raise CurrentBoardError(f"{section} item items must be a list")
    items = [_clean_text(item) for item in nested if _clean_text(item)]
    children_value = value.get("children", [])
    if children_value is None:
        children_value = []
    if not isinstance(children_value, list):
        raise CurrentBoardError(f"{section} item children must be a list")
    children: list[dict[str, str]] = []
    for child in children_value:
        if not isinstance(child, dict):
            raise CurrentBoardError(f"{section} child must be a mapping")
        child_title_value = child.get("title")
        child_detail_value = child.get("detail")
        if not isinstance(child_title_value, str) or not isinstance(child_detail_value, str):
            raise CurrentBoardError(f"{section} child title and detail must be strings")
        child_title = _clean_text(child_title_value)
        child_detail = _clean_text(child_detail_value)
        if not child_title or not child_detail:
            raise CurrentBoardError(f"{section} child requires title and detail")
        children.append({"title": child_title, "detail": child_detail})
    return {"title": title, "detail": detail, "items": items[:24], "children": children[:24]}


def load_current_board(board_path: Path) -> dict[str, Any]:
    if not board_path.is_file():
        raise CurrentBoardError("current board source must be an existing file")
    if board_path.is_symlink():
        raise CurrentBoardError("current board source must not be a symlink")
    try:
        loaded = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CurrentBoardError(f"current board source could not be read: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CurrentBoardError("current board source must contain a mapping")
    schema_version = _clean_text(loaded.get("schema_version"))
    if schema_version not in {"0.1", "0.1.0"}:
        raise CurrentBoardError("unsupported current board schema_version")
    title = _clean_text(loaded.get("title")) or "Stray AI Current Board"
    updated_at = _clean_text(loaded.get("updated_at")) or "unknown"

    now_value = loaded.get("now")
    if not isinstance(now_value, dict):
        raise CurrentBoardError("current board must define exactly one NOW mapping")
    notes_value = now_value.get("notes", [])
    if notes_value is None:
        notes_value = []
    if not isinstance(notes_value, list):
        raise CurrentBoardError("NOW notes must be a list")
    now_title = _clean_text(now_value.get("title"))
    purpose_value = now_value.get("purpose")
    if not isinstance(purpose_value, str) or not _clean_text(purpose_value):
        raise CurrentBoardError("NOW purpose must be a non-empty scalar string")
    purpose = _clean_text(purpose_value)
    stage = _clean_text(now_value.get("stage"))
    next_action = _clean_text(now_value.get("next_action"))
    authorized = now_value.get("implementation_authorized")
    if not now_title or not stage or not next_action or not isinstance(authorized, bool):
        raise CurrentBoardError(
            "NOW requires title, stage, next_action, and boolean implementation_authorized"
        )
    now = {
        "title": now_title,
        "purpose": purpose,
        "stage": stage,
        "next_action": next_action,
        "implementation_authorized": authorized,
        "issue": _clean_text(now_value.get("issue")),
        "notes": [_clean_text(item) for item in notes_value if _clean_text(item)][:12],
    }

    sections: dict[str, list[dict[str, Any]]] = {}
    for key in _SECTION_KEYS:
        raw = loaded.get(key, [])
        if raw is None:
            raw = []
        if not isinstance(raw, list):
            raise CurrentBoardError(f"{key} must be a list")
        sections[key] = [_normalize_item(item, section=key) for item in raw]

    return {
        "schema_version": schema_version,
        "title": title,
        "updated_at": updated_at,
        "now": now,
        **sections,
    }


def _latest_valid_json(directory: Path) -> tuple[dict[str, Any] | None, int]:
    if not directory.is_dir():
        return None, 0
    latest: dict[str, Any] | None = None
    invalid = 0
    for path in sorted(directory.glob("*.json")):
        value = _read_json_object(path)
        if value is None:
            invalid += 1
        else:
            latest = value
    return latest, invalid


def _visit_count(agent_dir: Path, state: dict[str, Any]) -> int:
    value = state.get("visit_count")
    if isinstance(value, int) and value >= 0:
        return value
    visits_dir = agent_dir / "visits"
    if not visits_dir.is_dir():
        return 0
    return sum(1 for path in visits_dir.glob("*.json") if _read_json_object(path) is not None)


def _request_status_counts(agent_dir: Path) -> tuple[dict[str, int], int]:
    request_dir = agent_dir / "visit_requests"
    if not request_dir.is_dir():
        return {}, 0
    counts: dict[str, int] = {}
    invalid = 0
    for path in sorted(request_dir.glob("*.json")):
        value = _read_json_object(path)
        if value is None:
            invalid += 1
            continue
        status = _clean_text(value.get("status"), limit=80) or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts, invalid


def build_live_state(agent_dir: Path) -> dict[str, Any]:
    if not agent_dir.is_dir():
        raise CurrentBoardError("agent directory must exist")
    state = _read_json_object(agent_dir / "state.json") or {}
    agent_id = _clean_text(state.get("id"), limit=120) or _clean_text(agent_dir.name, limit=120)
    status = _clean_text(state.get("status"), limit=80) or "unknown"
    current_location = state.get("current_location")
    if status == "resting" and not current_location:
        presence = "home"
    elif status == "visiting":
        presence = "visiting"
    elif current_location:
        presence = "away"
    else:
        presence = "unknown"

    wake, invalid_wake_count = _latest_valid_json(agent_dir / "wake_checks")
    venue = (wake or {}).get("venue")
    venue = venue if isinstance(venue, dict) else {}
    wake_summary = {
        "available": wake is not None,
        "checked_at": _clean_text((wake or {}).get("checked_at"), limit=80),
        "decision": _clean_text((wake or {}).get("decision"), limit=80),
        "candidate_venue_id": _clean_text(venue.get("candidate_venue_id"), limit=120),
        "comparison_scope": _clean_text(venue.get("comparison_scope"), limit=120),
        "invalid_file_count": invalid_wake_count,
    }
    request_counts, invalid_request_count = _request_status_counts(agent_dir)
    pending_count = request_counts.get("pending_human_approval", 0)

    return {
        "agent_id": agent_id,
        "status": status,
        "presence": presence,
        "visit_count": _visit_count(agent_dir, state),
        "latest_wake": wake_summary,
        "request_status_counts": request_counts,
        "pending_request_count": pending_count,
        "invalid_request_count": invalid_request_count,
    }


def _render_item(item: dict[str, Any]) -> str:
    detail = f'<p class="detail">{html.escape(item["detail"])}</p>' if item["detail"] else ""
    nested = ""
    if item["items"]:
        nested = '<ul class="nested">' + "".join(
            f"<li>{html.escape(entry)}</li>" for entry in item["items"]
        ) + "</ul>"
    if item["children"]:
        children = "".join(
            '<li class="board-child">'
            f'<strong>{html.escape(child["title"])}</strong>'
            f'<p class="detail">{html.escape(child["detail"])}</p></li>'
            for child in item["children"]
        )
        return (
            '<li class="board-group">'
            f'<strong class="board-group-title">{html.escape(item["title"])}</strong>'
            f'{detail}<ul class="board-children">{children}</ul></li>'
        )
    return f'<li><strong>{html.escape(item["title"])}</strong>{detail}{nested}</li>'


def _render_section(title: str, items: list[dict[str, Any]], *, class_name: str = "") -> str:
    body = (
        "<ul>" + "".join(_render_item(item) for item in items) + "</ul>"
        if items
        else '<p class="empty">項目なし</p>'
    )
    return f'<section class="panel {html.escape(class_name)}"><h2>{html.escape(title)}</h2>{body}</section>'


def render_current_board_html(
    board: dict[str, Any],
    live: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> str:
    generated = generated_at or datetime.now(_JST)
    now = board["now"]
    authorized_text = "実装承認済み" if now["implementation_authorized"] else "実装未承認"
    issue = f'<span class="meta-chip">{html.escape(now["issue"])}</span>' if now["issue"] else ""
    notes = ""
    if now["notes"]:
        notes = '<ul class="now-notes">' + "".join(
            f"<li>{html.escape(item)}</li>" for item in now["notes"]
        ) + "</ul>"

    wake = live["latest_wake"]
    wake_value = (
        f'{html.escape(wake["decision"] or "unknown")}<small>{html.escape(wake["checked_at"])}</small>'
        if wake["available"]
        else "未記録"
    )
    venue_value = html.escape(wake["candidate_venue_id"] or "—")
    request_summary = ", ".join(
        f"{html.escape(key)} {value}" for key, value in sorted(live["request_status_counts"].items())
    ) or "なし"

    sections_html = "".join(
        [
            _render_section("NEXT", board["next"], class_name="next"),
            _render_section("HOLD / WAIT", board["hold"], class_name="hold"),
            _render_section("RECENTLY DONE", board["recently_done"], class_name="done"),
            _render_section("PARKING LOT", board["parking_lot"], class_name="parking"),
            _render_section("NOT DOING", board["not_doing"], class_name="not-doing"),
        ]
    )

    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(board["title"])}</title>
{favicon_link_html()}
<style>
{cyberpunk_css()}
:root {{ color-scheme: dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; line-height: 1.55; }}
main {{ width: min(1120px, calc(100% - 32px)); margin: 24px auto 48px; padding: 28px; }}
header {{ margin-bottom: 24px; }}
h1 {{ margin: 0 0 8px; font-size: clamp(1.8rem, 5vw, 3.3rem); letter-spacing: -0.04em; }}
.subtitle, .generated {{ color: var(--muted); margin: 4px 0; }}
.readonly {{ border: 1px solid var(--line); background:var(--panel); border-radius: 12px; padding: 10px 14px; display: inline-block; margin-top: 12px; }}
.now {{ position:relative;border: 1px solid rgba(255,230,109,.62); border-left:4px solid var(--yellow); background:linear-gradient(135deg,rgba(255,230,109,.12),var(--panel) 48%); box-shadow:inset 0 0 24px rgba(255,230,109,.035),0 0 26px rgba(255,230,109,.08); border-radius: 4px 18px 18px 4px; padding: 22px; margin-bottom: 20px; }}
.now h2 {{ margin: 0 0 8px; font-size: .85rem; letter-spacing: .18em; color: var(--yellow); }}
.now h3 {{ margin: 0; font-size: clamp(1.45rem, 4vw, 2.35rem); }}
.now-purpose {{ margin:8px 0 0;color:var(--text);max-width:78ch; }}
.now-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }}
.now-cell, .metric {{ background: rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.06);border-radius: 6px; padding: 14px; }}
.label {{ display: block; color: var(--muted); font-size: .78rem; letter-spacing: .08em; margin-bottom: 4px; }}
.meta-chip {{ display: inline-block; border: 1px solid var(--line-magenta); color:var(--magenta); border-radius: 999px; padding: 3px 9px; margin-top: 10px; font-size: .82rem; }}
.live {{ margin: 20px 0;padding:16px 18px;border-left:2px solid var(--cyan);border-right:1px solid var(--line);background:linear-gradient(90deg,rgba(57,246,255,.08),rgba(8,14,22,.82));box-shadow:inset 0 0 22px rgba(57,246,255,.025); }}
.live h2, .panel h2 {{ font-size: .85rem; letter-spacing: .16em; color: var(--cyan); }}
.live > a {{display:inline-block;margin-top:12px;color:var(--cyan);text-underline-offset:3px}}
.metrics {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
.metric strong {{ display: block; font-size: 1.15rem; overflow-wrap: anywhere; }}.live .metric{{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:rgba(5,12,18,.72)}}
.metric small {{ display: block; color: #aaa; font-size: .75rem; margin-top: 3px; }}
.boards {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
.panel {{ --section-accent:var(--cyan);position:relative;border: 1px solid var(--line); border-top:2px solid var(--section-accent);border-radius: 3px 14px 14px 14px; padding: 18px; background:linear-gradient(150deg,color-mix(in srgb,var(--section-accent) 6%,transparent),var(--panel) 34%); box-shadow:inset 0 0 20px rgba(255,255,255,.012),0 0 18px rgba(57,246,255,.035); }}
.panel h2{{color:var(--section-accent)}}.next{{--section-accent:var(--cyan)}}.hold{{--section-accent:var(--yellow)}}.done{{--section-accent:#6dffb2}}.parking{{--section-accent:var(--magenta)}}.not-doing{{--section-accent:#ff8c9d}}
.panel ul {{ margin: 0; padding-left: 1.2rem; }}
.panel li + li {{ margin-top: 10px; }}
.detail {{ margin: 2px 0 0; color: var(--muted); }}
.nested {{ margin-top: 5px !important; color: var(--muted); }}
.board-group {{list-style:none;margin:16px 0 0 -1.2rem!important;border:1px solid var(--line-magenta);border-left:3px solid var(--magenta);padding:14px;background:rgba(255,79,216,.035)}}
.board-group-title {{color:var(--magenta);letter-spacing:.04em}}.board-children {{display:grid;gap:8px;margin-top:12px!important;padding:0!important;list-style:none}}.board-child{{margin:0!important;padding:10px 12px 10px 16px;border-left:1px solid var(--cyan);background:rgba(57,246,255,.035)}}.board-child::before{{content:"↳";color:var(--cyan);margin-right:8px}}
.empty {{ color: #777; }}
.footer-note {{ margin-top: 24px; color: #888; font-size: .88rem; }}
@media (max-width: 820px) {{
  .now-grid, .metrics, .boards {{ grid-template-columns: 1fr; }}
  main {{ width: min(100% - 12px, 1120px); margin:8px auto 24px;padding:18px 12px 28px; }}
}}
</style>
</head>
<body>
<main class="terminal-shell current-board-shell">
<header class="title-zone">
<div class="title-row">{inline_title_mark_svg()}<h1>{html.escape(board["title"])}</h1></div>
<p class="subtitle">全体像・現在地・次の一手を一枚で見る暫定Current-State interface</p>
<p class="generated">計画更新: {html.escape(board["updated_at"])} ／ 生成: {html.escape(generated.isoformat(timespec="seconds"))}</p>
<p class="readonly">このページは読み取り専用です。ここから承認・取消し・wake・Visitは実行できません。</p>
</header>
<section class="now">
<h2>NOW</h2>
<h3>{html.escape(now["title"])}</h3>
<p class="now-purpose">{html.escape(now["purpose"])}</p>
{issue}
<div class="now-grid">
<div class="now-cell"><span class="label">STAGE</span><strong>{html.escape(now["stage"])}</strong></div>
<div class="now-cell"><span class="label">NEXT ACTION</span><strong>{html.escape(now["next_action"])}</strong></div>
<div class="now-cell"><span class="label">AUTHORIZATION</span><strong>{html.escape(authorized_text)}</strong></div>
</div>
{notes}
</section>
<section class="live">
<h2>LIVE</h2>
<div class="metrics">
<div class="metric"><span class="label">VISITOR</span><strong>{html.escape(live["agent_id"])}</strong><small>{html.escape(live["status"])} / {html.escape(live["presence"])}</small></div>
<div class="metric"><span class="label">LATEST WAKE</span><strong>{wake_value}</strong><small>{venue_value} / {html.escape(wake["comparison_scope"] or "scope unknown")}</small></div>
<div class="metric"><span class="label">PENDING REQUESTS</span><strong>{live["pending_request_count"]}</strong><small>{request_summary}</small></div>
<div class="metric"><span class="label">VISITS</span><strong>{live["visit_count"]}</strong><small>persistent counter</small></div>
<div class="metric"><span class="label">INVALID LOCAL RECORDS</span><strong>{wake["invalid_file_count"] + live["invalid_request_count"]}</strong><small>wake / request files skipped</small></div>
</div>
<a href="../index.html">Stray AI · 訪問レポートを見る</a>
</section>
<div class="boards">{sections_html}</div>
<p class="footer-note">手動生成・HTMLのみ。Visit Reportとは分離され、外部fetch、scheduler、自動publishはありません。</p>
</main>
</body>
</html>
'''


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


def _safe_destination(report_root: Path) -> Path:
    if not report_root.is_dir():
        raise CurrentBoardError("report root must be an existing directory")
    root = report_root.resolve()
    current_dir = root / _PUBLISHED_RELATIVE_PATH.parent
    if current_dir.exists() and current_dir.is_symlink():
        raise CurrentBoardError("current directory must not be a symlink")
    current_dir.mkdir(parents=True, exist_ok=True)
    resolved_dir = current_dir.resolve()
    try:
        resolved_dir.relative_to(root)
    except ValueError as exc:
        raise CurrentBoardError("current directory escapes the report root") from exc
    destination = resolved_dir / _PUBLISHED_RELATIVE_PATH.name
    if destination.exists() and destination.is_symlink():
        raise CurrentBoardError("published current board must not be a symlink")
    json_files = sorted(
        path.relative_to(root).as_posix()
        for path in resolved_dir.glob("*.json*")
        if path.is_file()
    )
    if json_files:
        raise CurrentBoardError(
            "current board directory contains JSON-like files: " + ", ".join(json_files)
        )
    return destination


def _assert_safe_html(rendered: str) -> None:
    lowered = rendered.lower()
    found = [marker for marker in _FORBIDDEN_HTML_MARKERS if marker.lower() in lowered]
    if found:
        raise CurrentBoardError(
            "rendered current board failed the safety check: " + ", ".join(found)
        )
    if "このページは読み取り専用です" not in rendered:
        raise CurrentBoardError("rendered current board lost its read-only notice")


def publish_current_board(
    *,
    board_path: Path,
    agent_dir: Path,
    report_root: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    board = load_current_board(board_path)
    live = build_live_state(agent_dir.resolve())
    rendered = render_current_board_html(board, live, generated_at=generated_at)
    _assert_safe_html(rendered)
    destination = _safe_destination(report_root)
    _atomic_write_text(destination, rendered)
    return {
        "published": True,
        "html_output": str(destination),
        "gateway_path": "/stray-ai/current/index.html",
        "now": board["now"]["title"],
        "agent_status": live["status"],
        "pending_request_count": live["pending_request_count"],
        "visit_count": live["visit_count"],
        "boundaries": {
            "read_only": True,
            "venue_content_read": False,
            "contains_controls": False,
            "json_published": False,
            "automatic_publish": False,
            "wake_invoked": False,
            "visit_invoked": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-publish-current-board")
    parser.add_argument("--board", type=Path, required=True)
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        result = publish_current_board(
            board_path=args.board,
            agent_dir=args.agent,
            report_root=args.report_root,
        )
    except CurrentBoardError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
