from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from .report_archive import generate_archive

_COMMIT = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_GITHUB_REPOSITORY = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$"
)


@dataclass(frozen=True, slots=True)
class SourceCoordinates:
    venue_label: str
    repository_url: str
    repository_display: str
    commit: str
    branch: str | None
    captured_at: str | None
    snapshot_root: Path

    def page_path(self, location: Any) -> str | None:
        if not location:
            return None
        try:
            path = Path(str(location)).resolve()
            return path.relative_to(self.snapshot_root.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            return None

    def page_url(self, location: Any) -> str | None:
        relative = self.page_path(location)
        if relative is None:
            return None
        encoded = quote(relative, safe="/-._~")
        return f"{self.repository_url}/blob/{self.commit}/{encoded}"


def _metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip():
            values[key.strip()] = value.strip()
    return values


def _repository(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    match = _GITHUB_REPOSITORY.fullmatch(value)
    if match is None:
        return None
    owner, repository = match.groups()
    repository = repository.removesuffix(".git")
    return f"https://github.com/{owner}/{repository}", f"{owner}/{repository}"


def _venue_label(snapshot_root: Path, recorded: str | None = None) -> str:
    if recorded:
        label = recorded.strip()
        if 1 <= len(label) <= 120 and all(character.isprintable() for character in label):
            return label
    raw = snapshot_root.parent.name or "Unknown venue"
    return raw.replace("_", " ").replace("-", " ").strip().title()


def resolve_source_coordinates(visit: dict[str, Any]) -> SourceCoordinates | None:
    entrance = visit.get("entrance")
    if not entrance:
        return None
    try:
        entrance_path = Path(str(entrance)).resolve()
    except (OSError, RuntimeError):
        return None

    candidates = [entrance_path.parent, *entrance_path.parents]
    for root in candidates[:8]:
        metadata_path = root / "SNAPSHOT.txt"
        if not metadata_path.is_file():
            continue
        try:
            values = _metadata(metadata_path)
        except OSError:
            return None
        commit = values.get("source_commit", "")
        repository = _repository(values.get("source_repository"))
        if repository is None or not _COMMIT.fullmatch(commit):
            return None
        if root.name.lower() != commit.lower():
            return None
        try:
            entrance_path.relative_to(root.resolve())
        except (OSError, RuntimeError, ValueError):
            return None
        repository_url, repository_display = repository
        return SourceCoordinates(
            venue_label=_venue_label(root, values.get("venue_label")),
            repository_url=repository_url,
            repository_display=repository_display,
            commit=commit.lower(),
            branch=values.get("source_branch") or None,
            captured_at=values.get("captured_at") or None,
            snapshot_root=root.resolve(),
        )
    return None


def _external_link(soup: BeautifulSoup, label: str, url: str) -> Tag:
    anchor = soup.new_tag(
        "a",
        href=url,
        target="_blank",
        rel="noopener noreferrer",
        attrs={"class": "source-external"},
    )
    anchor.string = label
    return anchor


def _append_style(soup: BeautifulSoup, css: str) -> None:
    style = soup.new_tag("style")
    style.string = css
    if soup.head is not None:
        soup.head.append(style)


def augment_visit_report(
    html: str,
    visit: dict[str, Any],
    source: SourceCoordinates | None,
) -> str:
    if source is None:
        return html
    soup = BeautifulSoup(html, "html.parser")
    steps = visit.get("steps", []) if isinstance(visit.get("steps"), list) else []
    nodes = soup.select(".route .node")
    for node, step in zip(nodes, steps, strict=False):
        if not isinstance(step, dict):
            continue
        url = source.page_url(step.get("location"))
        title = node.select_one(".title")
        if url is None or title is None:
            continue
        label = title.get_text(" ", strip=True)
        title.clear()
        title.append(_external_link(soup, f"{label} ↗", url))
        source_path = source.page_path(step.get("location"))
        if source_path:
            path = node.select_one(".path")
            if path is not None:
                path.string = source_path

    grid = soup.select_one(".grid")
    if grid is not None:
        section = soup.new_tag("section", attrs={"class": "panel source-panel"})
        heading = soup.new_tag("h2")
        heading.string = "Source"
        section.append(heading)
        metrics = soup.new_tag("div", attrs={"class": "metrics"})

        def add_metric(label: str, value: str | Tag) -> None:
            row = soup.new_tag("div", attrs={"class": "metric"})
            name = soup.new_tag("span")
            name.string = label
            strong = soup.new_tag("strong")
            if isinstance(value, Tag):
                strong.append(value)
            else:
                strong.string = value
            row.extend([name, strong])
            metrics.append(row)

        add_metric(
            "Venue",
            _external_link(soup, f"{source.venue_label} ↗", source.repository_url),
        )
        add_metric("Repository", source.repository_display)
        add_metric("Observed commit", source.commit[:12])
        if source.captured_at:
            add_metric("Snapshot captured", source.captured_at)
        entrance_url = source.page_url(visit.get("entrance"))
        entrance_path = source.page_path(visit.get("entrance"))
        if entrance_url and entrance_path:
            add_metric(
                "Entrance",
                _external_link(soup, f"{entrance_path} ↗", entrance_url),
            )
        section.append(metrics)
        record = next(
            (
                candidate
                for candidate in grid.find_all("section", recursive=False)
                if candidate.find("h2") and candidate.find("h2").get_text(strip=True) == "Record"
            ),
            None,
        )
        if record is not None:
            record.insert_before(section)
        else:
            grid.append(section)

    _append_style(
        soup,
        ".source-external{color:inherit;text-decoration:none}.source-external:hover{color:var(--accent)}"
        ".source-panel strong{overflow-wrap:anywhere}",
    )
    return str(soup)


def augment_index(
    html: str,
    records: dict[str, tuple[dict[str, Any], SourceCoordinates | None]],
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    linked = False
    for card in soup.select("article.visit-card"):
        local = card.select_one(".visit-main h2 a[href]")
        if local is None:
            continue
        report_name = str(local.get("href") or "")
        record = records.get(report_name)
        if record is None:
            continue
        _, source = record
        if source is None:
            continue
        coordinate = soup.new_tag("p", attrs={"class": "source-coordinate"})
        coordinate.append(
            _external_link(
                soup,
                f"{source.repository_display} ↗",
                source.repository_url,
            )
        )
        coordinate.append(soup.new_tag("br"))
        commit = soup.new_tag("span")
        commit.string = f"observed {source.commit[:12]}"
        coordinate.append(commit)
        main = card.select_one(".visit-main")
        if main is not None:
            main.append(coordinate)
            linked = True
    if linked:
        _append_style(
            soup,
            ".source-coordinate{margin:10px 0 0;color:var(--muted);font-size:12px;line-height:1.55}"
            ".source-coordinate a{color:var(--text);text-decoration:none}"
            ".source-coordinate a:hover{color:var(--accent)}",
        )
    return str(soup)


def _load_visit(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def generate_source_aware_archive(
    visits_dir: Path,
    output_dir: Path,
    state_path: Path | None = None,
) -> dict[str, Any]:
    result = generate_archive(visits_dir, output_dir, state_path)
    records: dict[str, tuple[dict[str, Any], SourceCoordinates | None]] = {}
    linked_count = 0
    for report_value in result.get("report_files", []):
        report_path = Path(str(report_value))
        visit_path = visits_dir / f"{report_path.stem}.json"
        visit = _load_visit(visit_path)
        if visit is None:
            continue
        source = resolve_source_coordinates(visit)
        records[report_path.name] = (visit, source)
        if source is None:
            continue
        report_path.write_text(
            augment_visit_report(report_path.read_text(encoding="utf-8"), visit, source),
            encoding="utf-8",
        )
        linked_count += 1

    report_files = [Path(str(value)) for value in result.get("report_files", [])]
    latest_value = result.get("latest_report")
    if report_files and latest_value:
        shutil.copyfile(report_files[0], Path(str(latest_value)))

    index_path = Path(str(result["index_file"]))
    index_path.write_text(
        augment_index(index_path.read_text(encoding="utf-8"), records),
        encoding="utf-8",
    )
    return {**result, "source_linked_visit_count": linked_count}
