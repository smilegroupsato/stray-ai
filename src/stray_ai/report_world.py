from __future__ import annotations

import math
import os
from collections import Counter
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any, Iterable

from .report_sources import SourceCoordinates


@dataclass(frozen=True, slots=True)
class WorldIndividual:
    agent_id: str
    display_name: str | None
    status: str
    visit_count: int


@dataclass(frozen=True, slots=True)
class WorldVisitRecord:
    agent_id: str
    report_name: str
    visit: dict[str, Any]
    source: SourceCoordinates | None


@dataclass(slots=True)
class ObservedPlace:
    key: tuple[str, ...]
    label: str
    source: SourceCoordinates | None
    first_seen: tuple[str, str, str]
    visit_files: set[tuple[str, str]] = field(default_factory=set)
    individual_ids: set[str] = field(default_factory=set)

    @property
    def external_url(self) -> str | None:
        if self.source is None:
            return None
        return f"{self.source.repository_url}/tree/{self.source.commit}"


@dataclass(slots=True)
class ObservationRelation:
    agent_id: str
    place_key: tuple[str, ...]
    report_names: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""

    @property
    def visit_count(self) -> int:
        return len(self.report_names)


@dataclass(frozen=True, slots=True)
class WorldEvidence:
    agent_id: str
    place_key: tuple[str, ...]
    report_name: str
    started_at: str
    exit_reason: str


@dataclass(frozen=True, slots=True)
class ObservedWorld:
    individuals: tuple[WorldIndividual, ...]
    places: tuple[ObservedPlace, ...]
    relations: tuple[ObservationRelation, ...]
    evidence: tuple[WorldEvidence, ...]

    @property
    def visit_count(self) -> int:
        return len(self.evidence)


def _locations(visit: dict[str, Any]) -> list[Path]:
    values: list[Path] = []
    entrance = visit.get("entrance")
    if entrance:
        try:
            values.append(Path(str(entrance)).resolve())
        except (OSError, RuntimeError):
            pass
    steps = visit.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict) or not step.get("location"):
                continue
            try:
                values.append(Path(str(step["location"])).resolve())
            except (OSError, RuntimeError):
                continue
    return values


def _local_identity(
    agent_id: str,
    report_name: str,
    visit: dict[str, Any],
) -> tuple[str, ...]:
    locations = _locations(visit)
    if locations:
        try:
            root = Path(os.path.commonpath([str(path.parent) for path in locations])).resolve()
            return ("local", agent_id, str(root))
        except (OSError, RuntimeError, ValueError):
            pass
    return ("local", agent_id, report_name)


def _place_key(record: WorldVisitRecord) -> tuple[str, ...]:
    source = record.source
    if source is not None:
        return ("source", source.repository_url, source.commit)
    return _local_identity(record.agent_id, record.report_name, record.visit)


def build_observed_world(
    individuals: Iterable[WorldIndividual],
    records: Iterable[WorldVisitRecord],
) -> ObservedWorld:
    ordered_individuals = tuple(sorted(individuals, key=lambda item: item.agent_id))
    ordered_records = sorted(
        records,
        key=lambda item: (
            str(item.visit.get("started_at") or ""),
            item.agent_id,
            item.report_name,
        ),
    )

    places: dict[tuple[str, ...], ObservedPlace] = {}
    relations: dict[tuple[str, tuple[str, ...]], ObservationRelation] = {}
    evidence: list[WorldEvidence] = []
    local_counts: Counter[str] = Counter()

    for record in ordered_records:
        started_at = str(record.visit.get("started_at") or "unknown")
        key = _place_key(record)
        place = places.get(key)
        if place is None:
            if record.source is None:
                local_counts[record.agent_id] += 1
                number = local_counts[record.agent_id]
                label = (
                    f"Local habitat · {record.agent_id}"
                    if number == 1
                    else f"Local habitat {number} · {record.agent_id}"
                )
            else:
                label = record.source.venue_label
            place = ObservedPlace(
                key=key,
                label=label,
                source=record.source,
                first_seen=(started_at, record.agent_id, record.report_name),
            )
            places[key] = place

        place.visit_files.add((record.agent_id, record.report_name))
        place.individual_ids.add(record.agent_id)

        relation_key = (record.agent_id, key)
        relation = relations.get(relation_key)
        if relation is None:
            relation = ObservationRelation(
                agent_id=record.agent_id,
                place_key=key,
                first_seen=started_at,
                last_seen=started_at,
            )
            relations[relation_key] = relation
        relation.report_names.append(record.report_name)
        relation.last_seen = started_at

        evidence.append(
            WorldEvidence(
                agent_id=record.agent_id,
                place_key=key,
                report_name=record.report_name,
                started_at=started_at,
                exit_reason=str(record.visit.get("exit_reason") or "unknown"),
            )
        )

    ordered_places = tuple(sorted(places.values(), key=lambda item: item.first_seen))
    place_order = {place.key: index for index, place in enumerate(ordered_places)}
    ordered_relations = tuple(
        sorted(
            relations.values(),
            key=lambda item: (item.agent_id, place_order[item.place_key]),
        )
    )
    return ObservedWorld(
        individuals=ordered_individuals,
        places=ordered_places,
        relations=ordered_relations,
        evidence=tuple(evidence),
    )


def _place_label(place: ObservedPlace) -> str:
    if place.source is None:
        return place.label
    return f"{place.label} · {place.source.commit[:12]}"


def _graph(world: ObservedWorld) -> str:
    if not world.individuals or not world.places:
        return '<p class="empty-note">No preserved individual-to-place observation is available yet.</p>'

    row_count = max(len(world.individuals), len(world.places))
    width = 980
    height = max(260, 120 + row_count * 130)
    left_x = 180
    right_x = 760

    def positions(count: int, x: int) -> list[tuple[int, int]]:
        if count == 1:
            return [(x, height // 2)]
        gap = (height - 140) / max(1, count - 1)
        return [(x, round(70 + index * gap)) for index in range(count)]

    individual_positions = {
        individual.agent_id: position
        for individual, position in zip(
            world.individuals,
            positions(len(world.individuals), left_x),
            strict=False,
        )
    }
    place_positions = {
        place.key: position
        for place, position in zip(
            world.places,
            positions(len(world.places), right_x),
            strict=False,
        )
    }

    edges: list[str] = []
    for relation in world.relations:
        x1, y1 = individual_positions[relation.agent_id]
        x2, y2 = place_positions[relation.place_key]
        middle_x = (x1 + x2) / 2
        middle_y = (y1 + y2) / 2 - 8
        edges.append(
            f'<path class="world-edge" d="M {x1 + 92} {y1} C {middle_x} {y1}, '
            f'{middle_x} {y2}, {x2 - 112} {y2}"><title>{escape(relation.agent_id)} '
            f'observed {escape(_place_label(next(place for place in world.places if place.key == relation.place_key)))} '
            f'{relation.visit_count} time(s)</title></path>'
        )
        edges.append(
            f'<text class="edge-count" x="{middle_x}" y="{middle_y}" text-anchor="middle">'
            f'{relation.visit_count}×</text>'
        )

    individual_nodes: list[str] = []
    for individual in world.individuals:
        x, y = individual_positions[individual.agent_id]
        label = individual.display_name or individual.agent_id
        node = (
            f'<g class="world-node individual" transform="translate({x - 92},{y - 42})">'
            '<rect width="184" height="84" rx="18"></rect>'
            f'<text class="node-label" x="92" y="31" text-anchor="middle">{escape(label[:26])}</text>'
            f'<text class="node-path" x="92" y="53" text-anchor="middle">{escape(individual.agent_id)}</text>'
            f'<text class="node-count" x="92" y="70" text-anchor="middle">{individual.visit_count} preserved visit(s)</text>'
            '</g>'
        )
        individual_nodes.append(
            f'<a href="individuals/{escape(individual.agent_id, quote=True)}/index.html">{node}</a>'
        )

    place_nodes: list[str] = []
    for place in world.places:
        x, y = place_positions[place.key]
        subtitle = (
            f"{place.source.repository_display} · {place.source.commit[:12]}"
            if place.source is not None
            else "local-only observation"
        )
        node = (
            f'<g class="world-node place" transform="translate({x - 112},{y - 42})">'
            '<rect width="224" height="84" rx="18"></rect>'
            f'<text class="node-label" x="112" y="31" text-anchor="middle">{escape(place.label[:28])}</text>'
            f'<text class="node-path" x="112" y="53" text-anchor="middle">{escape(subtitle[:36])}</text>'
            f'<text class="node-count" x="112" y="70" text-anchor="middle">{len(place.visit_files)} preserved visit(s)</text>'
            '</g>'
        )
        if place.external_url:
            node = (
                f'<a href="{escape(place.external_url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{node}</a>'
            )
        place_nodes.append(node)

    return (
        '<div class="svg-wrap"><svg class="world-svg" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="world-title">'
        '<title id="world-title">Observed relationships between persistent individuals and places</title>'
        f'{"".join(edges)}{"".join(individual_nodes)}{"".join(place_nodes)}'
        '</svg></div>'
    )


def _relation_table(world: ObservedWorld) -> str:
    places = {place.key: place for place in world.places}
    rows: list[str] = []
    for relation in world.relations:
        place = places[relation.place_key]
        place_label = escape(_place_label(place))
        if place.external_url:
            place_label = (
                f'<a href="{escape(place.external_url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{place_label}</a>'
            )
        rows.append(
            '<tr>'
            f'<td><a href="individuals/{escape(relation.agent_id, quote=True)}/index.html">'
            f'{escape(relation.agent_id)}</a></td>'
            f'<td>{place_label}</td>'
            f'<td>{relation.visit_count}</td>'
            f'<td>{escape(relation.first_seen)}</td>'
            f'<td>{escape(relation.last_seen)}</td>'
            '</tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="5">No observation relationship recorded.</td></tr>')
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Individual</th><th>Observed place</th><th>Visits</th><th>First observed</th><th>Last observed</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _place_table(world: ObservedWorld) -> str:
    rows: list[str] = []
    for place in world.places:
        if place.source is None:
            repository = "Local-only"
            commit = "—"
        else:
            repository = (
                f'<a href="{escape(place.external_url or place.source.repository_url, quote=True)}" '
                'target="_blank" rel="noopener noreferrer">'
                f'{escape(place.source.repository_display)}</a>'
            )
            commit = f'<code>{escape(place.source.commit)}</code>'
        rows.append(
            '<tr>'
            f'<td>{escape(place.label)}</td>'
            f'<td>{repository}</td>'
            f'<td>{commit}</td>'
            f'<td>{len(place.individual_ids)}</td>'
            f'<td>{len(place.visit_files)}</td>'
            '</tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="5">No observed place recorded.</td></tr>')
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Observed place</th><th>Repository</th><th>Exact commit</th><th>Individuals</th><th>Visits</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _evidence_table(world: ObservedWorld) -> str:
    places = {place.key: place for place in world.places}
    rows: list[str] = []
    for item in world.evidence:
        report_href = f"individuals/{item.agent_id}/{item.report_name}"
        rows.append(
            '<tr>'
            f'<td><a href="{escape(report_href, quote=True)}">{escape(item.started_at)}</a></td>'
            f'<td>{escape(item.agent_id)}</td>'
            f'<td>{escape(_place_label(places[item.place_key]))}</td>'
            f'<td>{escape(item.exit_reason.replace("_", " "))}</td>'
            '</tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="4">No preserved Visit evidence recorded.</td></tr>')
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Visit evidence</th><th>Individual</th><th>Observed place</th><th>Exit</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_observed_world(world: ObservedWorld) -> str:
    individual_word = "individual" if len(world.individuals) == 1 else "individuals"
    place_word = "place" if len(world.places) == 1 else "places"
    visit_word = "Visit" if world.visit_count == 1 else "Visits"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stray AI — Observed World</title>
<style>
:root{{--bg:#0f1115;--panel:#171a21;--panel2:#1f2430;--text:#eef2f7;--muted:#9aa4b2;--line:#343b49;--accent:#d7ff62}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#1a2030,#0f1115 42%);color:var(--text);font-family:Inter,system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:48px 24px 72px}}a{{color:inherit}}.kicker{{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px}}
h1{{font-size:42px;margin:9px 0 10px}}.intro{{color:var(--muted);max-width:820px;line-height:1.7}}.summary{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0 30px}}
.summary span{{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:9px 13px;color:var(--muted)}}.panel{{background:rgba(23,26,33,.94);border:1px solid var(--line);border-radius:20px;padding:22px;margin-top:18px}}
.panel h2{{margin:0 0 16px;font-size:19px}}.svg-wrap{{overflow-x:auto}}.world-svg{{min-width:760px;width:100%;height:auto}}.world-edge{{fill:none;stroke:#586174;stroke-width:2.2}}
.edge-count{{fill:var(--accent);font-size:12px;font-weight:700}}.world-node rect{{fill:var(--panel2);stroke:var(--line);stroke-width:1.5}}.world-node.individual rect{{stroke:var(--accent)}}
.node-label{{fill:var(--text);font-size:14px;font-weight:700}}.node-path{{fill:var(--muted);font-size:10px}}.node-count{{fill:var(--accent);font-size:9px}}.empty-note{{color:var(--muted)}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}}td{{font-size:13px}}code{{overflow-wrap:anywhere}}
footer{{margin-top:24px;color:var(--muted);font-size:12px}}@media(max-width:600px){{h1{{font-size:34px}}}}
</style>
</head>
<body><main>
<div class="kicker"><a href="index.html">Stray AI · Visit Report v0</a></div>
<h1>Observed world</h1>
<p class="intro">A bounded view of which persistent individuals have observed which places. Lines mean preserved Visit evidence only. They do not infer travel between Visits or connections between places.</p>
<div class="summary">
<span>{len(world.individuals)} {individual_word}</span>
<span>{len(world.places)} observed {place_word}</span>
<span>{len(world.relations)} observation relations</span>
<span>{world.visit_count} preserved {visit_word}</span>
</div>
<section class="panel"><h2>Individual-to-place observations</h2>{_graph(world)}</section>
<section class="panel"><h2>Observation relationships</h2>{_relation_table(world)}</section>
<section class="panel"><h2>Observed places</h2>{_place_table(world)}</section>
<section class="panel"><h2>Chronological Visit evidence</h2>{_evidence_table(world)}</section>
<footer>Generated locally from bounded persistent records. This page cannot create, wake, schedule, or move an individual.</footer>
</main></body></html>"""


def write_observed_world(
    individuals: Iterable[WorldIndividual],
    records: Iterable[WorldVisitRecord],
    output_dir: Path,
) -> dict[str, Any]:
    world = build_observed_world(individuals, records)
    output_dir.mkdir(parents=True, exist_ok=True)
    world_path = output_dir / "world.html"
    world_path.write_text(render_observed_world(world), encoding="utf-8")
    return {
        "world_file": str(world_path),
        "world_individual_count": len(world.individuals),
        "world_visit_count": world.visit_count,
        "observed_place_count": len(world.places),
        "observed_relation_count": len(world.relations),
    }
