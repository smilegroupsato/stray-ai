from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import yaml

from .report_source_archive import generate_source_aware_archive

_AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NAMED_REPORT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}\.html$")


@dataclass(frozen=True, slots=True)
class IndividualReport:
    agent_id: str
    display_name: str | None
    status: str
    visit_count: int
    last_visit: str | None
    output_dir: Path
    archive_result: dict[str, Any]

    @property
    def relative_root(self) -> str:
        return f"individuals/{self.agent_id}"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_profile(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _display_name(profile: dict[str, Any]) -> str | None:
    value = profile.get("name")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _last_visit(visits_dir: Path) -> str | None:
    candidates: list[tuple[str, str]] = []
    for path in sorted(visits_dir.glob("*.json")):
        visit = _load_json(path)
        if not visit:
            continue
        candidates.append((str(visit.get("started_at") or ""), path.name))
    if not candidates:
        return None
    started_at, filename = max(candidates)
    return started_at or filename.removesuffix(".json")


def _discover_agent_dirs(agents_dir: Path) -> tuple[list[Path], list[str]]:
    valid: list[Path] = []
    skipped: list[str] = []
    if not agents_dir.is_dir():
        return valid, skipped
    for path in sorted(agents_dir.iterdir(), key=lambda candidate: candidate.name):
        if not path.is_dir():
            continue
        if _AGENT_ID.fullmatch(path.name) is None:
            skipped.append(path.name)
            continue
        valid.append(path)
    return valid, skipped


def _remove_primary_aliases(output_dir: Path) -> None:
    if output_dir.exists():
        for path in output_dir.iterdir():
            if path.is_file() and _NAMED_REPORT.fullmatch(path.name):
                path.unlink()
    for name in ("latest.html", "map.html", "visits.html"):
        path = output_dir / name
        if path.is_file():
            path.unlink()


def _copy_primary_aliases(primary: IndividualReport, output_dir: Path) -> list[str]:
    _remove_primary_aliases(output_dir)
    copied: list[str] = []

    source_index = primary.output_dir / "index.html"
    if source_index.is_file():
        shutil.copyfile(source_index, output_dir / "visits.html")
        copied.append("visits.html")

    for name in ("latest.html", "map.html"):
        source = primary.output_dir / name
        if source.is_file():
            shutil.copyfile(source, output_dir / name)
            copied.append(name)

    for value in primary.archive_result.get("report_files", []):
        source = Path(str(value))
        if not source.is_file() or _NAMED_REPORT.fullmatch(source.name) is None:
            continue
        shutil.copyfile(source, output_dir / source.name)
        copied.append(source.name)

    return copied


def _link(href: str, label: str) -> str:
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def render_collection_index(
    individuals: list[IndividualReport],
    primary_agent_id: str | None,
) -> str:
    cards: list[str] = []
    for individual in individuals:
        primary_badge = (
            '<span class="badge">PRIMARY</span>'
            if individual.agent_id == primary_agent_id
            else ""
        )
        identity = escape(individual.agent_id)
        if individual.display_name and individual.display_name != individual.agent_id:
            identity += f'<span class="name">{escape(individual.display_name)}</span>'

        links = [
            _link(f"{individual.relative_root}/index.html", "Visits"),
            _link(f"{individual.relative_root}/map.html", "Observed map"),
        ]
        latest_path = individual.output_dir / "latest.html"
        if latest_path.is_file():
            links.insert(1, _link(f"{individual.relative_root}/latest.html", "Latest"))

        last_visit = escape(individual.last_visit or "No visit recorded")
        visit_state = (
            '<span class="visit-state">NO VISITS YET</span>'
            if individual.visit_count == 0
            else ""
        )
        cards.append(
            '<article class="individual-card">'
            f'<div class="card-head"><div><h2>{identity}</h2>{primary_badge}</div>'
            f'<span class="status">{escape(individual.status)}</span></div>'
            '<div class="metrics">'
            f'<div><span>Visits</span><strong>{individual.visit_count}</strong></div>'
            f'<div><span>Last visit</span><strong>{last_visit}</strong></div>'
            '</div>'
            f"{visit_state}"
            f'<nav aria-label="Reports for {escape(individual.agent_id, quote=True)}">'
            + "".join(links)
            + '</nav></article>'
        )

    content = "".join(cards)
    if not content:
        content = (
            '<section class="empty">'
            '<h2>No persistent individuals observed</h2>'
            '<p>The collection is empty. No individual was created or awakened.</p>'
            '</section>'
        )

    total_visits = sum(individual.visit_count for individual in individuals)
    individual_word = "individual" if len(individuals) == 1 else "individuals"
    visit_word = "visit" if total_visits == 1 else "visits"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stray AI — Persistent Individuals</title>
<style>
:root{{--bg:#0f1115;--panel:#171a21;--panel2:#1f2430;--text:#eef2f7;--muted:#9aa4b2;--line:#343b49;--accent:#d7ff62}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#1a2030,#0f1115 42%);color:var(--text);font-family:Inter,system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:48px 24px 72px}}.kicker{{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px}}
h1{{font-size:42px;margin:9px 0 10px}}.intro{{color:var(--muted);max-width:720px;line-height:1.7}}.summary{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0 30px}}
.summary span{{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:9px 13px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}}.individual-card,.empty{{background:rgba(23,26,33,.94);border:1px solid var(--line);border-radius:20px;padding:22px}}
.card-head{{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}}h2{{margin:0;font-size:24px}}.name{{display:block;color:var(--muted);font-size:13px;font-weight:400;margin-top:5px}}
.badge{{display:inline-block;margin-top:10px;color:var(--accent);font-size:10px;letter-spacing:.14em}}.status{{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--accent);font-size:12px}}
.metrics{{display:grid;gap:10px;margin:22px 0}}.metrics div{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-bottom:10px}}
.metrics span{{color:var(--muted)}}.metrics strong{{font-size:13px;text-align:right;overflow-wrap:anywhere}}.visit-state{{display:block;margin:-6px 0 16px;color:var(--muted);font-size:10px;letter-spacing:.14em}}nav{{display:flex;gap:9px;flex-wrap:wrap}}nav a{{color:var(--text);text-decoration:none;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:9px 11px}}nav a:hover,nav a:focus-visible{{border-color:var(--accent);color:var(--accent)}}
.empty p,footer{{color:var(--muted)}}footer{{margin-top:24px;font-size:12px}}@media(max-width:600px){{h1{{font-size:34px}}}}
</style>
</head>
<body><main>
<div class="kicker">Stray AI · Visit Report v0</div>
<h1>Persistent individuals</h1>
<p class="intro">A read-only entrance to each visitor's preserved reports. Individuals remain separate; their memories, state, routes, and maps are not merged here.</p>
<div class="summary"><span>{len(individuals)} {individual_word}</span><span>{total_visits} preserved {visit_word}</span></div>
<div class="grid">{content}</div>
<footer>Generated locally from bounded persistent records. This page cannot create, wake, or move an individual.</footer>
</main></body></html>"""


def generate_report_collection(
    agents_dir: Path,
    output_dir: Path,
    primary_agent_id: str | None = None,
) -> dict[str, Any]:
    agents_dir = agents_dir.resolve()
    output_dir = output_dir.resolve()

    agent_dirs, skipped_agent_directories = _discover_agent_dirs(agents_dir)
    available_ids = {agent_dir.name for agent_dir in agent_dirs}
    if primary_agent_id is not None:
        if _AGENT_ID.fullmatch(primary_agent_id) is None:
            raise ValueError(f"invalid primary agent id: {primary_agent_id!r}")
        if primary_agent_id not in available_ids:
            raise FileNotFoundError(
                f"primary individual {primary_agent_id!r} was not found under {agents_dir}"
            )
    elif agent_dirs:
        primary_agent_id = agent_dirs[0].name

    output_dir.mkdir(parents=True, exist_ok=True)
    individuals_root = output_dir / "individuals"
    if individuals_root.exists():
        shutil.rmtree(individuals_root)
    individuals_root.mkdir(parents=True)

    individuals: list[IndividualReport] = []
    for agent_dir in agent_dirs:
        agent_id = agent_dir.name
        individual_output = individuals_root / agent_id
        state_path = agent_dir / "state.json"
        state = _load_json(state_path)
        profile = _load_profile(agent_dir / "profile.yml")
        archive_result = generate_source_aware_archive(
            agent_dir / "visits",
            individual_output,
            state_path if state_path.is_file() else None,
        )
        individuals.append(
            IndividualReport(
                agent_id=agent_id,
                display_name=_display_name(profile),
                status=str(state.get("status") or "unknown"),
                visit_count=int(archive_result.get("visit_count") or 0),
                last_visit=_last_visit(agent_dir / "visits"),
                output_dir=individual_output,
                archive_result=archive_result,
            )
        )

    primary = next(
        (
            individual
            for individual in individuals
            if individual.agent_id == primary_agent_id
        ),
        None,
    )
    compatibility_files = (
        _copy_primary_aliases(primary, output_dir) if primary is not None else []
    )
    if primary is None:
        _remove_primary_aliases(output_dir)

    collection_index = output_dir / "index.html"
    collection_index.write_text(
        render_collection_index(individuals, primary_agent_id),
        encoding="utf-8",
    )

    return {
        "collection_index_file": str(collection_index),
        "individual_count": len(individuals),
        "total_visit_count": sum(individual.visit_count for individual in individuals),
        "primary_agent_id": primary_agent_id,
        "compatibility_files": compatibility_files,
        "skipped_agent_directories": skipped_agent_directories,
        "individuals": [
            {
                "agent_id": individual.agent_id,
                "visit_count": individual.visit_count,
                "status": individual.status,
                "last_visit": individual.last_visit,
                "index_file": str(individual.output_dir / "index.html"),
                "latest_report": individual.archive_result.get("latest_report"),
                "map_file": individual.archive_result.get("map_file"),
                "observed_venue_count": individual.archive_result.get(
                    "observed_venue_count", 0
                ),
                "observed_node_count": individual.archive_result.get(
                    "observed_node_count", 0
                ),
                "observed_edge_count": individual.archive_result.get(
                    "observed_edge_count", 0
                ),
            }
            for individual in individuals
        ],
    }
