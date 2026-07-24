from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from .brand import cyberpunk_css, favicon_link_html, inline_title_mark_svg

_SAFE_RECORD = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}\.json$")


def _load_records(rummages_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not rummages_dir.is_dir():
        return records
    for path in sorted(rummages_dir.glob("*.json")):
        if _SAFE_RECORD.fullmatch(path.name) is None:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("schema") == "stray-rummage-v1":
            records.append(value)
    return records


def _list(items: Any, *, empty: str) -> str:
    if not isinstance(items, list):
        return f"<p>{escape(empty)}</p>"
    clean = [escape(str(item)) for item in items if str(item).strip()]
    return "<ul>" + "".join(f"<li>{item}</li>" for item in clean) + "</ul>" if clean else f"<p>{escape(empty)}</p>"


def _document_rows(documents: Any) -> str:
    if not isinstance(documents, list):
        return ""
    rows: list[str] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        mode = str(document.get("reading_mode") or "cover-skimming")
        path = escape(str(document.get("path") or "unknown"))
        title = escape(str(document.get("title") or path))
        note = escape(str(document.get("cover_note") or ""))
        deep = document.get("deep_reading")
        deep_html = ""
        if isinstance(deep, dict):
            law = escape(str(deep.get("local_law") or ""))
            residue = escape(str(deep.get("residue") or ""))
            deep_html = (
                f'<p><span>Local law</span>{law or "—"}</p>'
                f'<p><span>Residue</span>{residue or "—"}</p>'
            )
        rows.append(
            '<article class="document">'
            f'<div><strong>{title}</strong><code>{path}</code></div>'
            f'<span class="mode">{escape(mode)}</span>'
            f'{f"<p class=cover>{note}</p>" if note else ""}'
            f"{deep_html}"
            "</article>"
        )
    return "".join(rows)


def render_rummages(
    records: list[dict[str, Any]],
    *,
    agent_id: str,
) -> str:
    newest = sorted(
        records,
        key=lambda record: str(record.get("started_at") or ""),
        reverse=True,
    )
    cards: list[str] = []
    for record in newest:
        started = escape(str(record.get("started_at") or "unknown"))
        model = escape(str(record.get("brain_model") or "unknown"))
        repository = record.get("repository")
        repository_name = (
            escape(str(repository.get("name") or "unknown"))
            if isinstance(repository, dict)
            else "unknown"
        )
        trace = escape(str(record.get("trace") or "No Trace left."))
        sunlight = escape(
            str(record.get("sunlit_thought") or "No sunlit thought remained.")
        )
        survey = escape(str(record.get("survey_observation") or ""))
        cards.append(
            '<section class="rummage">'
            f'<header><div><span class="time">{started}</span><h2>{repository_name}</h2></div>'
            f'<span class="model">{model}</span></header>'
            f'<p class="survey">{survey}</p>'
            '<div class="documents">'
            f'{_document_rows(record.get("documents"))}'
            "</div>"
            '<div class="residue-grid">'
            f'<section><h3>余白メモ</h3>{_list(record.get("margin_notes"), empty="No margin notes.")}</section>'
            f'<section><h3>記憶</h3>{_list(record.get("memories_added"), empty="No memory remained.")}</section>'
            f'<section><h3>日の当たる場所で</h3><p>{sunlight}</p></section>'
            f'<section><h3>Trace</h3><p>{trace}</p></section>'
            "</div></section>"
        )
    content = "".join(cards) or (
        '<section class="empty"><p>No runtime rummage has entered the shelf-gap log yet.</p>'
        "<p>The earlier hand-authored prototype is not counted here.</p></section>"
    )
    identity = escape(agent_id)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Rummages of {identity}</title>
{favicon_link_html()}
<style>
{cyberpunk_css()}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,sans-serif}}main{{max-width:1040px;margin:24px auto 48px;padding:42px 28px 64px}}
h1{{font-size:42px;margin:0}}.intro,.time,.survey,.empty,.document code{{color:var(--muted)}}.intro{{line-height:1.7;max-width:760px}}
.rummage,.empty{{margin-top:28px;padding:24px;background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--magenta);border-radius:4px 16px 16px 4px}}
.rummage>header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}}h2{{margin:6px 0 0}}.model,.mode{{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--cyan);font-size:12px}}
.documents{{display:grid;gap:12px;margin-top:22px}}.document{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:16px;background:rgba(0,0,0,.18);border:1px solid var(--line);border-radius:10px}}
.document code{{display:block;margin-top:5px;overflow-wrap:anywhere}}.document p{{grid-column:1/-1;margin:4px 0;line-height:1.6}}.document p span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.1em}}
.residue-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}}.residue-grid section{{padding:18px;border:1px solid var(--line);border-radius:12px;background:rgba(0,0,0,.12)}}h3{{margin:0 0 10px;color:var(--accent)}}li,p{{line-height:1.65}}
@media(max-width:720px){{h1{{font-size:34px}}.residue-grid{{grid-template-columns:1fr}}.document{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main class="terminal-shell">
<div class="title-row">{inline_title_mark_svg()}<div><div class="time">Stray AI · Document Rummage v1</div><h1>The Rummages of {identity}</h1></div></div>
<p class="intro">表紙をめくり、選んだ文書に深く潜り、持ち帰った記憶を読む場所。Visitとは別の、リポジトリ内での文書漁りです。</p>
{content}
</main></body></html>"""


def generate_rummage_report(
    rummages_dir: Path,
    output_file: Path,
    *,
    agent_id: str,
) -> dict[str, Any]:
    records = _load_records(rummages_dir)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        render_rummages(records, agent_id=agent_id),
        encoding="utf-8",
    )
    return {
        "rummage_count": len(records),
        "rummage_report": str(output_file),
    }
