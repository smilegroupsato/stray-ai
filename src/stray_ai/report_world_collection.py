from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from .report_collection import generate_report_collection
from .report_source_archive import resolve_visit_source
from .report_world import WorldIndividual, WorldVisitRecord, write_observed_world


_COLLECTION_UI_CSS = """
html,body{width:100%;max-width:100%;min-width:0;overflow-x:hidden}
main{width:min(100%,1100px);max-width:100%;min-width:0;margin:0 auto;padding:48px 24px 72px}
main>*,.summary,.world-link,.grid,.grid>*,.individual-card,.empty,.card-head,.metrics,.metrics div,nav{min-width:0;max-width:100%}
.grid{grid-template-columns:minmax(0,1fr);width:100%}
.grid>*{width:100%}
.card-head,.metrics div{flex-wrap:wrap}
.metrics strong{min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word}
nav{flex-wrap:wrap}
@media(max-width:680px){
 main{padding:28px 14px 48px}
 h1{font-size:32px}
 .card-head{flex-direction:column}
 .metrics div{align-items:flex-start;flex-direction:column;gap:5px}
 .metrics strong{text-align:left}
}
"""

_STATE_LABELS = {
    "unborn": "未誕生",
    "awake": "覚醒中",
    "visiting": "訪問中",
    "resting": "休息中",
    "unknown": "不明",
}


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


def _leading_count(text: str) -> str:
    value = text.strip().split(maxsplit=1)[0] if text.strip() else "0"
    return value if value.isdigit() else "0"


def _localize_collection(soup: BeautifulSoup) -> None:
    if soup.title is not None:
        soup.title.string = "Stray AI — 永続個体"

    kicker = soup.select_one(".kicker")
    if kicker is not None:
        kicker.string = "Stray AI · 訪問レポート v0"

    heading = soup.find("h1")
    if heading is not None:
        heading.string = "永続個体"

    intro = soup.select_one(".intro")
    if intro is not None:
        intro.string = (
            "保存された各訪問者のレポートへ入る、読み取り専用の入口。"
            "個体ごとの記憶・状態・経路・地図は、ここでは混合しない。"
        )

    summary_items = soup.select(".summary span")
    if len(summary_items) >= 1:
        summary_items[0].string = f"{_leading_count(summary_items[0].get_text())} 個体"
    if len(summary_items) >= 2:
        summary_items[1].string = (
            f"{_leading_count(summary_items[1].get_text())}件の保存済み訪問"
        )

    world_link = soup.select_one('a[href="world.html"]')
    if world_link is not None:
        world_link.string = "観測された世界地図"

    for badge in soup.select(".individual-card .badge"):
        if badge.get_text(" ", strip=True) == "PRIMARY":
            badge.string = "主個体"

    for status in soup.select(".individual-card .status"):
        value = status.get_text(" ", strip=True)
        status.string = _STATE_LABELS.get(value, value)

    for label in soup.select(".individual-card .metrics span"):
        value = label.get_text(" ", strip=True)
        label.string = {
            "Visits": "訪問回数",
            "Last visit": "最終訪問",
        }.get(value, value)

    for link in soup.select(".individual-card nav a"):
        value = link.get_text(" ", strip=True)
        link.string = {
            "Visits": "訪問一覧",
            "Latest": "最新レポート",
            "Observed map": "観測地図",
        }.get(value, value)

    empty_heading = soup.select_one(".empty h2")
    if empty_heading is not None:
        empty_heading.string = "観測された永続個体はまだいない"
    empty_paragraph = soup.select_one(".empty p")
    if empty_paragraph is not None:
        empty_paragraph.string = (
            "コレクションは空であり、個体の生成や覚醒は行われていない。"
        )

    footer = soup.find("footer")
    if footer is not None:
        footer.string = (
            "境界づけられた永続記録からローカル生成。"
            "このページは個体を生成・覚醒・移動させない。"
        )


def augment_collection_with_world_link(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one('a[href="world.html"]') is None:
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

    if soup.select_one("style#collection-ui-v0") is None:
        style = soup.new_tag("style", id="collection-ui-v0")
        style.string = (
            ".world-link{margin:-12px 0 28px}.world-link a{display:inline-block;"
            "color:var(--text);text-decoration:none;background:var(--panel2);"
            "border:1px solid var(--line);border-radius:12px;padding:10px 13px}"
            ".world-link a:hover,.world-link a:focus-visible{border-color:var(--accent);"
            "color:var(--accent)}"
            + _COLLECTION_UI_CSS
        )
        if soup.head is not None:
            soup.head.append(style)

    _localize_collection(soup)
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
