from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from .report_collection import generate_report_collection
from .report_source_archive import resolve_visit_source
from .report_world import WorldIndividual, WorldVisitRecord, write_observed_world


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _display_name(agent_dir: Path) -> str | None:
    try:
        value = yaml.safe_load((agent_dir / "profile.yml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(value, dict) or value.get("name") is None:
        return None
    text = str(value["name"]).strip()
    return text or None


def augment_collection_with_world_link(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one('a[href="world.html"]') is not None:
        return str(soup)

    link = soup.new_tag("a", href="world.html")
    link.string = "Observed world map"
    nav = soup.new_tag("nav", attrs={"class": "world-link"})
    nav.append(link)

    summary = soup.select_one(".summary")
    if summary is not None:
        summary.insert_after(nav)
    elif soup.main is not None:
        soup.main.insert(0, nav)
    elif soup.body is not None:
        soup.body.append(nav)
    else:
        soup.append(nav)

    style = soup.new_tag("style")
    style.string = (
        ".world-link{margin:-12px 0 28px}.world-link a{display:inline-block;"
        "color:var(--text);text-decoration:none;background:var(--panel2);"
        "border:1px solid var(--line);border-radius:12px;padding:10px 13px}"
        ".world-link a:hover,.world-link a:focus-visible{border-color:var(--accent);"
        "color:var(--accent)}"
    )
    if soup.head is not None:
        soup.head.append(style)
    return str(soup)


def generate_world_report_collection(
    agents_dir: Path,
    output_dir: Path,
    primary_agent_id: str | None = None,
) -> dict[str, Any]:
    agents_dir = agents_dir.resolve()
    output_dir = output_dir.resolve()
    result = generate_report_collection(agents_dir, output_dir, primary_agent_id)

    individuals: list[WorldIndividual] = []
    records: list[WorldVisitRecord] = []

    for item in result.get("individuals", []):
        if not isinstance(item, dict) or not item.get("agent_id"):
            continue
        agent_id = str(item["agent_id"])
        agent_dir = agents_dir / agent_id
        individuals.append(
            WorldIndividual(
                agent_id=agent_id,
                display_name=_display_name(agent_dir),
                status=str(item.get("status") or "unknown"),
                visit_count=int(item.get("visit_count") or 0),
            )
        )

        visits_dir = agent_dir / "visits"
        individual_output = output_dir / "individuals" / agent_id
        if not visits_dir.is_dir():
            continue
        for visit_path in sorted(visits_dir.glob("*.json")):
            report_name = f"{visit_path.stem}.html"
            if not (individual_output / report_name).is_file():
                continue
            visit = _load_json(visit_path)
            if visit is None:
                continue
            records.append(
                WorldVisitRecord(
                    agent_id=agent_id,
                    report_name=report_name,
                    visit=visit,
                    source=resolve_visit_source(visit),
                )
            )

    world_result = write_observed_world(individuals, records, output_dir)
    collection_index = Path(str(result["collection_index_file"]))
    collection_index.write_text(
        augment_collection_with_world_link(
            collection_index.read_text(encoding="utf-8")
        ),
        encoding="utf-8",
    )
    return {**result, **world_result}
