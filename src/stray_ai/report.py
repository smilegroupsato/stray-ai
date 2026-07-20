from __future__ import annotations

import argparse
import json
import shutil
from html import escape
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_visit(visits_dir: Path) -> Path:
    visits = sorted(visits_dir.glob("*.json"))
    if not visits:
        raise FileNotFoundError(f"no visit records found in {visits_dir}")
    return visits[-1]


def _short_path(value: str | None) -> str:
    return Path(value).name if value else "—"


def render_report(visit: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    state = state or {}
    steps = list(visit.get("steps", []))
    route_nodes: list[str] = []
    brain_cards: list[str] = []
    for index, step in enumerate(steps, start=1):
        action = str(step.get("action", "observe"))
        terminal_class = " terminal" if action in {"leave", "leave_trace"} else ""
        badge = (
            "TRACE"
            if action == "leave_trace"
            else "LEAVE"
            if action == "leave"
            else f"STEP {step.get('step', index)}"
        )
        title_value = str(step.get("title", "Untitled"))
        title = escape(title_value)
        location = escape(_short_path(str(step.get("location", ""))))
        route_nodes.append(
            f'<div class="node{terminal_class}">'
            f'<div class="badge">{escape(badge)}</div>'
            f'<div class="title">{title}</div>'
            f'<div class="path">{location}</div>'
            "</div>"
        )

        brain = step.get("brain")
        if isinstance(brain, dict):
            status = escape(str(brain.get("status", "unknown")))
            model = escape(str(brain.get("model") or visit.get("brain_model") or "host"))
            observation = escape(str(brain.get("observation") or "No observation recorded."))
            error = brain.get("error")
            error_html = (
                f'<p class="brain-error">{escape(str(error))}</p>' if error else ""
            )
            brain_cards.append(
                '<div class="card brain-card">'
                f'<div class="brain-head"><strong>Step {index} · {title}</strong>'
                f'<span class="brain-status {status}">{status}</span></div>'
                f'<p>{observation}</p>'
                f'<div class="path">{model}</div>'
                f'{error_html}'
                '</div>'
            )
    route_html = (
        '<div class="arrow">→</div>'.join(route_nodes)
        or '<p class="muted">No steps recorded.</p>'
    )
    brain_html = "".join(brain_cards) or '<p class="muted">No brain decisions recorded.</p>'

    exit_reason = str(visit.get("exit_reason", "unknown"))
    exit_label = (
        "Left silently"
        if exit_reason == "left_silently"
        else "Trace carried home"
        if exit_reason == "trace_carried_home"
        else "Left safely · brain rejected"
        if exit_reason == "brain_failed_safe_exit"
        else exit_reason.replace("_", " ").title()
    )
    memories = [str(item) for item in visit.get("memories_added", [])]
    trace_file = visit.get("trace_file")
    trace_text = (
        f"Carried home: {_short_path(str(trace_file))}"
        if trace_file
        else "No trace carried home."
    )
    memory_text = (
        "<br>".join(escape(item) for item in memories)
        if memories
        else "No new memory was selected."
    )

    if exit_reason == "brain_failed_safe_exit":
        summary = f"{len(steps)}つの場所を歩き、判断を受理できなかったため、安全に退出した。"
    elif exit_reason == "left_silently" and not trace_file and not memories:
        summary = f"{len(steps)}つの場所を歩き、何も持ち帰らず、静かに退出した。"
    else:
        summary = (
            f"{len(steps)}つの場所を歩き、{len(memories)}件を記憶し、"
            f"{'Traceを持ち帰った。' if trace_file else 'Traceは残さなかった。'}"
        )

    metrics = {
        "Places": len(steps),
        "Exit": exit_reason,
        "Trace": "Yes" if trace_file else "None",
        "New memories": len(memories),
        "Model": visit.get("brain_model") or "deterministic mock",
    }
    state_metrics = {
        "Status": state.get("status", "—"),
        "Visit count": state.get("visit_count", "—"),
        "Fatigue": state.get("fatigue", "—"),
        "Current location": _short_path(state.get("current_location")),
    }

    def metric_rows(items: dict[str, Any]) -> str:
        return "".join(
            f'<div class="metric"><span>{escape(str(key))}</span>'
            f'<strong>{escape(str(value))}</strong></div>'
            for key, value in items.items()
        )

    started_at = escape(str(visit.get("started_at", "unknown")))
    agent_id = escape(str(visit.get("agent_id", "unknown")))
    backend = escape(str(visit.get("backend", "unknown")))
    visit_file = escape(_short_path(str(visit.get("visit_file", ""))))
    entrance = escape(_short_path(str(visit.get("entrance", ""))))

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Visit Report — {agent_id}</title>
<style>
:root{{--bg:#0f1115;--panel:#171a21;--panel2:#1f2430;--text:#eef2f7;--muted:#9aa4b2;--line:#343b49;--accent:#d7ff62;--bad:#ff9d9d}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#1a2030,#0f1115 42%);color:var(--text);font-family:Inter,system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:48px 24px 72px}}header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:28px}}
.kicker{{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px;margin-bottom:8px}}h1{{font-size:40px;margin:0 0 8px}}
.subtitle,.muted{{color:var(--muted)}}.status{{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:10px 14px;color:var(--accent)}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:18px}}.panel{{background:rgba(23,26,33,.94);border:1px solid var(--line);border-radius:20px;padding:22px}}
.wide{{grid-column:1/-1}}.panel h2{{margin:0 0 18px;font-size:18px}}.route{{display:flex;align-items:center;overflow-x:auto;padding:8px 2px 14px}}
.node{{min-width:170px;border:1px solid var(--line);background:var(--panel2);border-radius:16px;padding:16px}}.node.terminal{{border-color:var(--accent)}}
.badge{{color:var(--accent);font-size:11px;letter-spacing:.14em;margin-bottom:10px}}.title{{font-weight:700;font-size:17px;margin-bottom:6px}}
.path{{color:var(--muted);font-size:12px}}.arrow{{color:var(--muted);font-size:24px;padding:0 12px}}.metrics{{display:grid;gap:12px}}
.metric{{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding-bottom:12px}}.metric:last-child{{border-bottom:0;padding-bottom:0}}
.metric span{{color:var(--muted)}}.result{{display:grid;gap:12px}}.card{{border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:var(--panel2)}}
.card strong{{display:block;margin-bottom:5px}}.card p{{margin:0 0 7px;color:var(--muted)}}.note{{margin-top:18px;border-left:3px solid var(--accent);padding:12px 14px;background:rgba(215,255,98,.06);color:#e9f7b9;border-radius:8px}}
.brain-head{{display:flex;justify-content:space-between;gap:16px;align-items:center}}.brain-status{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent)}}
.brain-status.rejected,.brain-error{{color:var(--bad)!important}}.brain-card+.brain-card{{margin-top:12px}}
footer{{margin-top:18px;color:var(--muted);font-size:12px}}@media(max-width:800px){{header{{flex-direction:column}}.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}h1{{font-size:32px}}}}
</style>
</head>
<body>
<main>
<header>
<div><div class="kicker">Stray AI · Visit Report v0</div><h1>{agent_id}</h1>
<div class="subtitle">{started_at} · backend: {backend}</div></div>
<div class="status">{escape(exit_label)}</div>
</header>
<div class="grid">
<section class="panel"><h2>Walk</h2><div class="route">{route_html}</div><div class="note">{escape(summary)}</div></section>
<aside class="panel"><h2>Visit</h2><div class="metrics">{metric_rows(metrics)}</div></aside>
<section class="panel wide"><h2>Brain decisions</h2><div class="result">{brain_html}</div></section>
<section class="panel"><h2>What came home</h2><div class="result">
<div class="card"><strong>Trace</strong><p>{escape(trace_text)}</p></div>
<div class="card"><strong>Memory</strong><p>{memory_text}</p></div>
</div></section>
<section class="panel"><h2>Current state</h2><div class="metrics">{metric_rows(state_metrics)}</div></section>
<section class="panel"><h2>Record</h2><div class="metrics">
<div class="metric"><span>Entrance</span><strong>{entrance}</strong></div>
<div class="metric"><span>Visit file</span><strong>{visit_file}</strong></div>
</div></section>
</div>
<footer>Generated locally from the visitor's persistent devbox record.</footer>
</main>
</body>
</html>"""


def generate_report(
    visit_path: Path,
    output_dir: Path,
    state_path: Path | None = None,
) -> tuple[Path, Path]:
    visit = _load_json(visit_path)
    visit.setdefault("visit_file", str(visit_path))
    state = _load_json(state_path) if state_path and state_path.exists() else {}
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{visit_path.stem}.html"
    report_path.write_text(render_report(visit, state), encoding="utf-8")
    latest_path = output_dir / "latest.html"
    shutil.copyfile(report_path, latest_path)
    return report_path, latest_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-report")
    parser.add_argument("--visit", type=Path)
    parser.add_argument("--visits-dir", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    visit_path = args.visit
    if visit_path is None:
        if args.visits_dir is None:
            parser.error("provide --visit or --visits-dir")
        visit_path = _latest_visit(args.visits_dir)

    report_path, latest_path = generate_report(
        visit_path.resolve(),
        args.output_dir.resolve(),
        args.state.resolve() if args.state else None,
    )
    print(
        json.dumps(
            {"report_file": str(report_path), "latest_report": str(latest_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
