from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .brand import cyberpunk_css, favicon_link_html, inline_title_mark_svg
from .report import render_report

_SAFE_STEM = re.compile(r"^[A-Za-z0-9._-]+$")
_SNAPSHOT_ID = re.compile(r"^[0-9a-fA-F]{32,64}$")


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root is not an object")
    return value


def _state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return _load_object(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _time_label(value: Any) -> str:
    text = str(value or "unknown")
    if "T" not in text:
        return text
    date, clock = text.split("T", 1)
    return f"{date} {clock}"


def _exit_label(value: Any) -> str:
    reason = str(value or "unknown")
    return {
        "left_silently": "Left silently",
        "trace_carried_home": "Trace carried home",
        "brain_failed_safe_exit": "Left safely · brain rejected",
        "place_limit": "Place limit reached",
    }.get(reason, reason.replace("_", " ").title())


def _venue_label(entrance: Any) -> str:
    if not entrance:
        return "Unknown venue"
    path = Path(str(entrance))
    parent = path.parent
    if _SNAPSHOT_ID.fullmatch(parent.name) and parent.parent.name:
        parent = parent.parent
    name = parent.name or "Unknown venue"
    return name.replace("_", " ").replace("-", " ").strip().title()


def _model_label(visit: dict[str, Any]) -> str:
    return str(visit.get("brain_model") or "deterministic mock")


def _record_card(path: Path, visit: dict[str, Any], *, latest: bool) -> str:
    report_name = f"{path.stem}.html"
    href = escape(quote(report_name, safe="-_.~"), quote=True)
    started = escape(_time_label(visit.get("started_at")))
    backend = escape(str(visit.get("backend") or "unknown"))
    model = escape(_model_label(visit))
    venue = escape(_venue_label(visit.get("entrance")))
    result = escape(_exit_label(visit.get("exit_reason")))
    places = len(visit.get("steps", [])) if isinstance(visit.get("steps"), list) else 0
    memories = (
        len(visit.get("memories_added", []))
        if isinstance(visit.get("memories_added"), list)
        else 0
    )
    trace = "Trace" if visit.get("trace_file") else "No Trace"
    latest_badge = '<span class="latest-badge">LATEST</span>' if latest else ""
    return (
        '<article class="visit-card">'
        '<div class="visit-main">'
        f'<div class="visit-time">{started}{latest_badge}</div>'
        f'<h2><a href="{href}">{venue}</a></h2>'
        f'<p class="result">{result}</p>'
        '</div>'
        '<dl class="visit-facts">'
        f'<div><dt>Backend</dt><dd>{backend}</dd></div>'
        f'<div><dt>Model</dt><dd>{model}</dd></div>'
        f'<div><dt>Places</dt><dd>{places}</dd></div>'
        f'<div><dt>Memory</dt><dd>{memories}</dd></div>'
        f'<div><dt>Trace</dt><dd>{trace}</dd></div>'
        '</dl>'
        '</article>'
    )


def render_index(
    records: list[tuple[Path, dict[str, Any]]],
    state: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> str:
    state = state or {}
    newest_first = sorted(
        records,
        key=lambda item: (str(item[1].get("started_at") or ""), item[0].name),
        reverse=True,
    )
    latest_visit = newest_first[0][1] if newest_first else {}
    display_agent_id = escape(
        str(
            agent_id
            or latest_visit.get("agent_id")
            or state.get("agent_id")
            or state.get("id")
            or "stray-001"
        )
    )
    lifecycle = escape(str(state.get("status") or "unknown"))
    persistent_count = escape(str(state.get("visit_count", len(newest_first))))
    latest_time = escape(_time_label(latest_visit.get("started_at"))) if newest_first else "—"
    latest_result = (
        escape(_exit_label(latest_visit.get("exit_reason"))) if newest_first else "No visits yet"
    )
    cards = "".join(
        _record_card(path, visit, latest=index == 0)
        for index, (path, visit) in enumerate(newest_first)
    )
    if not cards:
        cards = (
            '<section class="empty">'
            '<p>No visit has entered the archive yet.</p>'
            '<p>Silence here is an observed absence, not an error.</p>'
            '</section>'
        )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Visits of {display_agent_id}</title>
{favicon_link_html()}
<style>
{cyberpunk_css()}
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,sans-serif}}
main{{max-width:980px;margin:24px auto 48px;padding:42px 28px 64px}}a{{color:inherit;text-decoration:none}}a:hover{{color:var(--accent)}}
.kicker{{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px;margin-bottom:10px}}h1{{font-size:42px;line-height:1.08;margin:0 0 10px}}
.intro{{color:var(--muted);max-width:680px;line-height:1.7;margin:0}}.state{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:30px 0}}
.state div,.visit-card,.empty{{background:var(--panel);border:1px solid var(--line);border-radius:4px 16px 16px 4px;box-shadow:inset 0 0 18px rgba(57,246,255,.018),0 0 20px rgba(57,246,255,.035)}}.state div{{padding:16px;border-top:2px solid var(--cyan)}}
.state span{{display:block;color:var(--muted);font-size:12px;margin-bottom:7px}}.state strong{{font-size:16px;overflow-wrap:anywhere}}
.archive-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:38px 0 16px}}.archive-head h2{{margin:0;font-size:22px}}.archive-head p{{margin:0;color:var(--muted);font-size:13px}}
.visits{{display:grid;gap:14px}}.visit-card{{position:relative;padding:20px 20px 20px 24px;display:grid;grid-template-columns:minmax(220px,1.1fr) 2fr;gap:24px;align-items:center;border-left:3px solid var(--magenta);background:linear-gradient(110deg,rgba(255,79,216,.055),var(--panel) 32%)}}
.visit-time{{color:var(--muted);font-size:13px;display:flex;align-items:center;gap:10px}}.latest-badge{{color:var(--accent);font-size:10px;letter-spacing:.12em}}
.visit-main h2{{font-size:22px;margin:8px 0 6px}}.result{{color:var(--muted);margin:0}}.visit-facts{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:0}}
.visit-facts div{{min-width:0}}dt{{color:var(--muted);font-size:11px;margin-bottom:5px}}dd{{margin:0;font-size:13px;overflow-wrap:anywhere}}.empty{{padding:28px;color:var(--muted)}}
footer{{margin-top:24px;color:var(--muted);font-size:12px}}@media(max-width:800px){{h1{{font-size:34px}}.state{{grid-template-columns:1fr 1fr}}.visit-card{{grid-template-columns:1fr}}.visit-facts{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<main class="terminal-shell visit-archive-shell">
<header class="title-zone">
<div class="kicker">Stray AI · Visit Report v0 · Archive</div>
<div class="title-row">{inline_title_mark_svg()}<h1>The Visits of {display_agent_id}</h1></div>
<p class="intro">A local observation window into one visitor's recorded passages. This page offers no controls and starts no movement.</p>
</header>
<section class="state" aria-label="Persistent state">
<div><span>Lifecycle</span><strong>{lifecycle}</strong></div>
<div><span>Persistent visit count</span><strong>{persistent_count}</strong></div>
<div><span>Visible records</span><strong>{len(newest_first)}</strong></div>
<div><span>Latest</span><strong>{latest_time}<br>{latest_result}</strong></div>
</section>
<div class="archive-head"><h2>Recorded visits</h2><p>Newest first · local relative links</p></div>
<section class="visits">{cards}</section>
<footer>Generated locally from preserved Visit JSON. Wake judgments are recorded separately.</footer>
</main>
</body>
</html>"""


def generate_archive(
    visits_dir: Path,
    output_dir: Path,
    state_path: Path | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    visits_dir = visits_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state = _state(state_path.resolve() if state_path else None)

    rendered: list[tuple[Path, dict[str, Any], Path]] = []
    skipped: list[str] = []
    for visit_path in sorted(visits_dir.glob("*.json")):
        if not _SAFE_STEM.fullmatch(visit_path.stem) or visit_path.stem in {"index", "latest"}:
            skipped.append(visit_path.name)
            continue
        try:
            visit = _load_object(visit_path)
            visit.setdefault("visit_file", str(visit_path))
            report_path = output_dir / f"{visit_path.stem}.html"
            report_path.write_text(render_report(visit, state), encoding="utf-8")
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError, AttributeError):
            skipped.append(visit_path.name)
            continue
        rendered.append((visit_path, visit, report_path))

    rendered.sort(
        key=lambda item: (str(item[1].get("started_at") or ""), item[0].name),
        reverse=True,
    )
    latest_path = output_dir / "latest.html"
    if rendered:
        shutil.copyfile(rendered[0][2], latest_path)
        latest_value: str | None = str(latest_path)
    else:
        latest_path.unlink(missing_ok=True)
        latest_value = None

    index_path = output_dir / "index.html"
    index_path.write_text(
        render_index(
            [(path, visit) for path, visit, _ in rendered],
            state,
            agent_id=agent_id,
        ),
        encoding="utf-8",
    )
    return {
        "index_file": str(index_path),
        "latest_report": latest_value,
        "report_files": [str(report_path) for _, _, report_path in rendered],
        "visit_count": len(rendered),
        "skipped_visit_files": skipped,
    }
