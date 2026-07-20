from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .report_archive import generate_archive
from .report_map import augment_index_with_map_link, write_observed_map
from .report_navigation import add_archive_link
from .report_sources import (
    SourceCoordinates,
    augment_index,
    augment_visit_report,
    resolve_source_coordinates,
)


def _load_visit(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _recorded_locations(visit: dict[str, Any]) -> list[str]:
    values: list[str] = []

    entrance = visit.get("entrance")
    if entrance:
        values.append(str(entrance))

    arrival_path = visit.get("arrival_path")
    if isinstance(arrival_path, list):
        values.extend(str(value) for value in arrival_path if value)

    steps = visit.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict) and step.get("location"):
                values.append(str(step["location"]))

    return list(dict.fromkeys(values))


def resolve_visit_source(visit: dict[str, Any]) -> SourceCoordinates | None:
    """Resolve one unambiguous trusted snapshot from all recorded visit locations.

    Older Visit records may have a legacy entrance while their recorded steps point
    into the immutable snapshot. Every candidate still passes the strict SNAPSHOT.txt,
    GitHub repository, commit, directory-identity, and containment checks implemented
    by resolve_source_coordinates.
    """

    sources: dict[tuple[str, str, str], SourceCoordinates] = {}
    for location in _recorded_locations(visit):
        candidate = dict(visit)
        candidate["entrance"] = location
        source = resolve_source_coordinates(candidate)
        if source is None:
            continue
        key = (
            source.repository_url,
            source.commit,
            str(source.snapshot_root.resolve()),
        )
        sources[key] = source

    if len(sources) != 1:
        return None
    return next(iter(sources.values()))


def generate_source_aware_archive(
    visits_dir: Path,
    output_dir: Path,
    state_path: Path | None = None,
) -> dict[str, Any]:
    result = generate_archive(visits_dir, output_dir, state_path)
    records: dict[str, tuple[dict[str, Any], SourceCoordinates | None]] = {}
    linked_files: list[str] = []
    unlinked_files: list[str] = []

    for report_value in result.get("report_files", []):
        report_path = Path(str(report_value))
        visit_path = visits_dir / f"{report_path.stem}.json"
        visit = _load_visit(visit_path)
        if visit is None:
            unlinked_files.append(visit_path.name)
            continue

        source = resolve_visit_source(visit)
        records[report_path.name] = (visit, source)
        report_html = add_archive_link(report_path.read_text(encoding="utf-8"))

        if source is None:
            report_path.write_text(report_html, encoding="utf-8")
            unlinked_files.append(visit_path.name)
            continue

        report_path.write_text(
            augment_visit_report(report_html, visit, source),
            encoding="utf-8",
        )
        linked_files.append(visit_path.name)

    report_files = [Path(str(value)) for value in result.get("report_files", [])]
    latest_value = result.get("latest_report")
    if report_files and latest_value:
        shutil.copyfile(report_files[0], Path(str(latest_value)))

    index_path = Path(str(result["index_file"]))
    index_html = augment_index(index_path.read_text(encoding="utf-8"), records)
    index_path.write_text(augment_index_with_map_link(index_html), encoding="utf-8")
    map_result = write_observed_map(records, output_dir)

    return {
        **result,
        **map_result,
        "source_linked_visit_count": len(linked_files),
        "source_linked_visit_files": linked_files,
        "source_unlinked_visit_files": unlinked_files,
    }
