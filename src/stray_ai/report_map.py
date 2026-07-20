from __future__ import annotations

import math
import os
from collections import Counter
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .report_sources import SourceCoordinates


@dataclass(slots=True)
class ObservedNode:
    key: str
    label: str
    display_path: str
    external_url: str | None
    first_seen: tuple[str, int, str]
    visit_files: set[str] = field(default_factory=set)
    entrance_count: int = 0
    terminal_count: int = 0


@dataclass(frozen=True, slots=True)
class ObservedRoute:
    report_name: str
    started_at: str
    exit_reason: str
    node_keys: tuple[str, ...]


@dataclass(slots=True)
class ObservedVenue:
    key: tuple[str, ...]
    label: str
    source: SourceCoordinates | None
    local_root: Path | None
    first_seen: tuple[str, str]
    nodes: dict[str, ObservedNode] = field(default_factory=dict)
    edges: Counter[tuple[str, str]] = field(default_factory=Counter)
    routes: list[ObservedRoute] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ObservedMap:
    venues: tuple[ObservedVenue, ...]
    visit_count: int
    node_count: int
    edge_count: int


def _steps(visit: dict[str, Any]) -> list[dict[str, Any]]:
    value = visit.get("steps")
    if not isinstance(value, list):
        return []
    return [step for step in value if isinstance(step, dict) and step.get("location")]


def _local_root(steps: list[dict[str, Any]], visit: dict[str, Any]) -> Path | None:
    values: list[Path] = []
    for step in steps:
        try:
            values.append(Path(str(step["location"])).resolve())
        except (OSError, RuntimeError):
            continue
    if not values and visit.get("entrance"):
        try:
            values.append(Path(str(visit["entrance"])).resolve())
        except (OSError, RuntimeError):
            pass
    if not values:
        return None
    try:
        return Path(os.path.commonpath([str(path.parent) for path in values])).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _source_venue_key(source: SourceCoordinates) -> tuple[str, ...]:
    return (
        "source",
        source.repository_url,
        source.commit,
        str(source.snapshot_root.resolve()),
    )


def _local_venue_key(root: Path | None, report_name: str) -> tuple[str, ...]:
    return ("local", str(root) if root is not None else report_name)


def _display_local_path(location: Any, root: Path | None) -> str:
    try:
        path = Path(str(location)).resolve()
        if root is not None:
            relative = path.relative_to(root.resolve()).as_posix()
            if relative and relative != ".":
                return relative
        return path.name or "Untitled"
    except (OSError, RuntimeError, ValueError):
        return Path(str(location)).name or "Untitled"


def _node_identity(
    location: Any,
    source: SourceCoordinates | None,
    local_root: Path | None,
) -> tuple[str, str, str | None]:
    if source is not None:
        relative = source.page_path(location)
        if relative is not None:
            return (
                f"source:{source.repository_url}@{source.commit}:{relative}",
                relative,
                source.page_url(location),
            )
    local_path = _display_local_path(location, local_root)
    try:
        internal = str(Path(str(location)).resolve())
    except (OSError, RuntimeError):
        internal = str(location)
    return f"local:{internal}", local_path, None


def build_observed_map(
    records: dict[str, tuple[dict[str, Any], SourceCoordinates | None]],
) -> ObservedMap:
    venues: dict[tuple[str, ...], ObservedVenue] = {}
    local_order: list[tuple[str, ...]] = []
    ordered_records = sorted(
        records.items(),
        key=lambda item: (str(item[1][0].get("started_at") or ""), item[0]),
    )

    for report_name, (visit, source) in ordered_records:
        steps = _steps(visit)
        started_at = str(visit.get("started_at") or "unknown")
        root = None if source is not None else _local_root(steps, visit)
        key = (
            _source_venue_key(source)
            if source is not None
            else _local_venue_key(root, report_name)
        )
        venue = venues.get(key)
        if venue is None:
            if source is not None:
                label = source.venue_label
            else:
                local_order.append(key)
                label = (
                    "Local first habitat"
                    if len(local_order) == 1
                    else f"Local venue {len(local_order)}"
                )
            venue = ObservedVenue(
                key=key,
                label=label,
                source=source,
                local_root=root,
                first_seen=(started_at, report_name),
            )
            venues[key] = venue

        route_keys: list[str] = []
        for step_index, step in enumerate(steps):
            node_key, display_path, external_url = _node_identity(
                step.get("location"), source, venue.local_root
            )
            title = str(step.get("title") or Path(display_path).name or "Untitled")
            node = venue.nodes.get(node_key)
            if node is None:
                node = ObservedNode(
                    key=node_key,
                    label=title,
                    display_path=display_path,
                    external_url=external_url,
                    first_seen=(started_at, step_index, display_path),
                )
                venue.nodes[node_key] = node
            node.visit_files.add(report_name)
            route_keys.append(node_key)

        if route_keys:
            venue.nodes[route_keys[0]].entrance_count += 1
            venue.nodes[route_keys[-1]].terminal_count += 1
            for left, right in zip(route_keys, route_keys[1:], strict=False):
                venue.edges[(left, right)] += 1

        venue.routes.append(
            ObservedRoute(
                report_name=report_name,
                started_at=started_at,
                exit_reason=str(visit.get("exit_reason") or "unknown"),
                node_keys=tuple(route_keys),
            )
        )

    ordered_venues = tuple(sorted(venues.values(), key=lambda venue: venue.first_seen))
    return ObservedMap(
        venues=ordered_venues,
        visit_count=len(ordered_records),
        node_count=sum(len(venue.nodes) for venue in ordered_venues),
        edge_count=sum(len(venue.edges) for venue in ordered_venues),
    )


def _svg(venue: ObservedVenue, index: int) -> str:
    nodes = sorted(venue.nodes.values(), key=lambda node: node.first_seen)
    if not nodes:
        return '<p class="empty-note">No observed pages were recorded for this venue.</p>'

    columns = min(4, max(1, math.ceil(math.sqrt(len(nodes)))))
    rows = math.ceil(len(nodes) / columns)
    width = max(520, columns * 240)
    height = max(220, rows * 170)
    positions: dict[str, tuple[int, int]] = {}
    for node_index, node in enumerate(nodes):
        row, column = divmod(node_index, columns)
        positions[node.key] = (120 + column * 240, 95 + row * 170)

    marker_id = f"arrow-{index}"
    edge_parts: list[str] = []
    for (left, right), count in sorted(
        venue.edges.items(),
        key=lambda item: (
            venue.nodes[item[0][0]].first_seen,
            venue.nodes[item[0][1]].first_seen,
        ),
    ):
        x1, y1 = positions[left]
        x2, y2 = positions[right]
        if y1 == y2:
            path = f"M {x1 + 78} {y1} L {x2 - 78} {y2}"
            label_x = (x1 + x2) / 2
            label_y = y1 - 10
        else:
            curve_x = (x1 + x2) / 2
            path = f"M {x1} {y1 + 38} Q {curve_x} {(y1 + y2) / 2} {x2} {y2 - 38}"
            label_x = curve_x
            label_y = (y1 + y2) / 2 - 8
        plural = "s" if count != 1 else ""
        edge_parts.append(
            f'<path class="map-edge" d="{path}" marker-end="url(#{marker_id})">'
            f"<title>{escape(venue.nodes[left].display_path)} to "
            f"{escape(venue.nodes[right].display_path)} · {count} traversal{plural}</title>"
            "</path>"
        )
        if count > 1:
            edge_parts.append(
                f'<text class="edge-count" x="{label_x}" y="{label_y}">{count}×</text>'
            )

    node_parts: list[str] = []
    for node in nodes:
        x, y = positions[node.key]
        classes = ["map-node"]
        if node.entrance_count:
            classes.append("entrance")
        if node.terminal_count:
            classes.append("terminal")
        subtitle = f"{len(node.visit_files)} visit"
        if len(node.visit_files) != 1:
            subtitle += "s"
        if node.entrance_count:
            subtitle += f" · entrance {node.entrance_count}"
        if node.terminal_count:
            subtitle += f" · terminal {node.terminal_count}"
        box = (
            f'<g class="{" ".join(classes)}" transform="translate({x - 82},{y - 42})">'
            '<rect width="164" height="84" rx="16"></rect>'
            f'<text class="node-label" x="82" y="32" text-anchor="middle">{escape(node.label[:24])}</text>'
            f'<text class="node-path" x="82" y="53" text-anchor="middle">{escape(node.display_path[:30])}</text>'
            f'<text class="node-count" x="82" y="70" text-anchor="middle">{escape(subtitle)}</text>'
            "</g>"
        )
        if node.external_url:
            box = (
                f'<a href="{escape(node.external_url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{box}</a>'
            )
        node_parts.append(box)

    title_id = f"venue-map-title-{index}"
    return (
        '<div class="svg-wrap">'
        f'<svg class="venue-svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id}">'
        f'<title id="{title_id}">Observed route map for {escape(venue.label)}</title>'
        "<defs>"
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z"></path></marker>'
        "</defs>"
        f'{"".join(edge_parts)}{"".join(node_parts)}'
        "</svg></div>"
    )


def _venue_source(venue: ObservedVenue) -> str:
    if venue.source is None:
        return '<p class="venue-source">Local-only observation · no external source coordinates</p>'
    source = venue.source
    return (
        '<p class="venue-source">'
        f'<a href="{escape(source.repository_url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{escape(source.repository_display)} ↗</a>'
        f' · observed commit <code>{escape(source.commit[:12])}</code>'
        "</p>"
    )


def _route_table(venue: ObservedVenue) -> str:
    rows: list[str] = []
    for route in sorted(venue.routes, key=lambda item: (item.started_at, item.report_name)):
        labels = [
            venue.nodes[key].display_path for key in route.node_keys if key in venue.nodes
        ]
        path = " → ".join(labels) if labels else "No mapped steps"
        rows.append(
            "<tr>"
            f'<td><a href="{escape(route.report_name, quote=True)}">{escape(route.started_at)}</a></td>'
            f"<td>{escape(path)}</td>"
            f"<td>{escape(route.exit_reason.replace('_', ' '))}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Visit</th><th>Observed route</th><th>Exit</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _node_table(venue: ObservedVenue) -> str:
    rows: list[str] = []
    for node in sorted(venue.nodes.values(), key=lambda item: item.first_seen):
        label = escape(node.display_path)
        if node.external_url:
            label = (
                f'<a href="{escape(node.external_url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{label} ↗</a>'
            )
        rows.append(
            "<tr>"
            f"<td>{label}</td>"
            f"<td>{len(node.visit_files)}</td>"
            f"<td>{node.entrance_count}</td>"
            f"<td>{node.terminal_count}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Observed page</th><th>Visits</th><th>Entrance</th><th>Terminal</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_observed_map(observed: ObservedMap) -> str:
    venue_sections: list[str] = []
    for index, venue in enumerate(observed.venues, start=1):
        venue_sections.append(
            f'<section class="venue" id="venue-{index}">'
            '<div class="venue-head"><div>'
            f'<div class="venue-number">VENUE {index}</div>'
            f"<h2>{escape(venue.label)}</h2>"
            f"{_venue_source(venue)}</div>"
            '<dl class="venue-facts">'
            f"<div><dt>Visits</dt><dd>{len(venue.routes)}</dd></div>"
            f"<div><dt>Pages</dt><dd>{len(venue.nodes)}</dd></div>"
            f"<div><dt>Transitions</dt><dd>{len(venue.edges)}</dd></div>"
            "</dl></div>"
            f"{_svg(venue, index)}"
            "<h3>Observed routes</h3>"
            f"{_route_table(venue)}"
            "<h3>Observed pages</h3>"
            f"{_node_table(venue)}"
            "</section>"
        )
    if not venue_sections:
        venue_sections.append(
            '<section class="empty"><p>No observed route has entered the map yet.</p>'
            "<p>This absence is preserved rather than filled with inferred geography.</p></section>"
        )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Observed Venue Map</title>
<style>
:root{{--bg:#0f1115;--panel:#171a21;--panel2:#1f2430;--text:#eef2f7;--muted:#9aa4b2;--line:#343b49;--accent:#d7ff62}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#1a2030,#0f1115 42%);color:var(--text);font-family:Inter,system-ui,sans-serif}}
main{{max-width:1120px;margin:auto;padding:52px 24px 80px}}a{{color:inherit}}a:hover,a:focus-visible{{color:var(--accent)}}
.kicker{{text-transform:uppercase;letter-spacing:.18em;font-size:12px;margin-bottom:10px}}.kicker a{{color:var(--accent);text-decoration:none}}
h1{{font-size:42px;line-height:1.08;margin:0 0 10px}}.intro{{color:var(--muted);max-width:760px;line-height:1.7;margin:0}}
.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:30px 0 40px}}.summary div,.venue,.empty{{background:rgba(23,26,33,.94);border:1px solid var(--line);border-radius:18px}}
.summary div{{padding:16px}}.summary span{{display:block;color:var(--muted);font-size:12px;margin-bottom:7px}}.summary strong{{font-size:18px}}
.venue{{padding:24px;margin-top:18px}}.venue-head{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}}.venue-number{{color:var(--accent);font-size:11px;letter-spacing:.14em}}
.venue h2{{font-size:28px;margin:7px 0}}.venue h3{{font-size:16px;margin:26px 0 10px}}.venue-source{{color:var(--muted);margin:0;overflow-wrap:anywhere}}.venue-source a{{text-decoration:none}}
.venue-facts{{display:grid;grid-template-columns:repeat(3,minmax(70px,1fr));gap:10px;margin:0}}.venue-facts div{{background:var(--panel2);border-radius:12px;padding:12px}}dt{{color:var(--muted);font-size:11px}}dd{{margin:5px 0 0;font-size:16px}}
.svg-wrap{{overflow-x:auto;margin-top:22px;border:1px solid var(--line);border-radius:16px;background:var(--panel2)}}.venue-svg{{min-width:620px;width:100%;height:auto;display:block}}
.map-edge{{fill:none;stroke:var(--muted);stroke-width:2;opacity:.72}}marker path{{fill:var(--muted)}}.edge-count{{fill:var(--accent);font-size:12px;text-anchor:middle}}
.map-node rect{{fill:#171a21;stroke:var(--line);stroke-width:2}}.map-node.entrance rect{{stroke:var(--accent)}}.map-node.terminal rect{{stroke-dasharray:5 3}}.node-label{{fill:var(--text);font-size:14px;font-weight:700}}.node-path,.node-count{{fill:var(--muted);font-size:9px}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;border-bottom:1px solid var(--line);padding:11px 9px;vertical-align:top}}th{{color:var(--muted);font-size:11px;font-weight:500}}td a{{text-decoration:none}}
.empty{{padding:28px;color:var(--muted)}}footer{{margin-top:24px;color:var(--muted);font-size:12px}}
@media(max-width:760px){{h1{{font-size:34px}}.summary{{grid-template-columns:1fr 1fr}}.venue-head{{flex-direction:column}}.venue-facts{{width:100%}}}}
</style>
</head>
<body>
<main>
<header>
<div class="kicker"><a href="index.html">Stray AI · Visit Report v0</a></div>
<h1>Observed Venue Map</h1>
<p class="intro">Only preserved passages are drawn here. Unvisited pages, inferred links, and the rest of each venue remain outside the map.</p>
</header>
<section class="summary" aria-label="Observed map summary">
<div><span>Visible visits</span><strong>{observed.visit_count}</strong></div>
<div><span>Observed venues</span><strong>{len(observed.venues)}</strong></div>
<div><span>Observed pages</span><strong>{observed.node_count}</strong></div>
<div><span>Observed transitions</span><strong>{observed.edge_count}</strong></div>
</section>
{"".join(venue_sections)}
<footer>Generated locally from preserved Visit JSON. This is observed geography, not a venue inventory.</footer>
</main>
</body>
</html>"""


def augment_index_with_map_link(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one('a[href="map.html"]') is not None:
        return str(soup)
    archive_head = soup.select_one(".archive-head")
    if archive_head is None:
        return html
    link = soup.new_tag("a", href="map.html", attrs={"class": "map-link"})
    link.string = "Observed venue map →"
    archive_head.append(link)
    style = soup.new_tag("style")
    style.string = (
        ".map-link{color:var(--accent);font-size:13px;text-decoration:none;white-space:nowrap}"
        ".map-link:hover,.map-link:focus-visible{text-decoration:underline}"
    )
    if soup.head is not None:
        soup.head.append(style)
    return str(soup)


def write_observed_map(
    records: dict[str, tuple[dict[str, Any], SourceCoordinates | None]],
    output_dir: Path,
) -> dict[str, Any]:
    observed = build_observed_map(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    map_path = output_dir / "map.html"
    map_path.write_text(render_observed_map(observed), encoding="utf-8")
    return {
        "map_file": str(map_path),
        "observed_venue_count": len(observed.venues),
        "observed_node_count": observed.node_count,
        "observed_edge_count": observed.edge_count,
    }
