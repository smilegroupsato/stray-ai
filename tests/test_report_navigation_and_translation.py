from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup

from stray_ai.report_translations import source_digest
from stray_ai.report_world_collection import generate_world_report_collection


def _write_agent(tmp_path: Path) -> tuple[Path, Path, str, str]:
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "stray-001"
    visits_dir = agent_dir / "visits"
    visits_dir.mkdir(parents=True)
    (agent_dir / "profile.yml").write_text(
        "id: stray-001\nname: unnamed\nkind: visitor\n",
        encoding="utf-8",
    )
    (agent_dir / "state.json").write_text(
        json.dumps({"status": "resting", "visit_count": 1}),
        encoding="utf-8",
    )

    venue = tmp_path / "venues" / "local"
    venue.mkdir(parents=True)
    entrance = venue / "README.md"
    terminal = venue / "END.md"
    entrance.write_text("# Entrance\n", encoding="utf-8")
    terminal.write_text("# End\n", encoding="utf-8")

    observation = "Trusted reception path selected by the host."
    memory = "Read AFTERHOURS.md and noticed the afterimage of the work."
    visit = {
        "agent_id": "stray-001",
        "started_at": "2026-07-21T13:05:24+09:00",
        "ended_at": "2026-07-21T13:06:40+09:00",
        "entrance": str(entrance),
        "backend": "command",
        "brain_model": "test-model",
        "steps": [
            {
                "step": 1,
                "location": str(entrance),
                "title": "Entrance",
                "action": "follow_arrival_path",
                "brain": {
                    "status": "accepted",
                    "model": "test-model",
                    "observation": observation,
                    "error": None,
                },
            },
            {
                "step": 2,
                "location": str(terminal),
                "title": "End",
                "action": "leave",
                "brain": {
                    "status": "accepted",
                    "model": "test-model",
                    "observation": "The silence feels complete.",
                    "error": None,
                },
            },
        ],
        "trace_file": None,
        "memories_added": [memory],
        "exit_reason": "left_silently",
    }
    visit_path = visits_dir / "2026-07-21_130524.json"
    visit_path.write_text(json.dumps(visit), encoding="utf-8")
    return agents_dir, visit_path, observation, memory


def _write_translations(tmp_path: Path, observation: str, memory: str) -> None:
    translations_dir = tmp_path / "report-translations"
    translations_dir.mkdir()
    value = {
        "version": 1,
        "language": "ja",
        "model": "test-translator",
        "translations": [
            {
                "source_sha256": source_digest(observation),
                "source": observation,
                "translation": "ホストが選んだ信頼済みの受け入れ経路を進んだ。",
            },
            {
                "source_sha256": source_digest(memory),
                "source": memory,
                "translation": "AFTERHOURS.mdを読み、作業の余像に気づいた。",
            },
        ],
    }
    (translations_dir / "stray-001.ja.json").write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )


def test_individual_namespace_has_directory_index_and_top_navigation(
    tmp_path: Path,
) -> None:
    agents_dir, _, _, _ = _write_agent(tmp_path)
    output_dir = tmp_path / "reports"

    result = generate_world_report_collection(agents_dir, output_dir, "stray-001")

    individuals_index = Path(result["individuals_index_file"])
    assert individuals_index == output_dir / "individuals" / "index.html"
    assert individuals_index.is_file()

    directory_soup = BeautifulSoup(
        individuals_index.read_text(encoding="utf-8"),
        "html.parser",
    )
    assert directory_soup.select_one('a[href="../index.html"]') is not None
    assert directory_soup.select_one('a[href="stray-001/index.html"]') is not None
    assert directory_soup.select_one('a[href="../world.html"]') is not None

    individual_dir = output_dir / "individuals" / "stray-001"
    for name in ("index.html", "map.html", "latest.html", "2026-07-21_130524.html"):
        soup = BeautifulSoup((individual_dir / name).read_text(encoding="utf-8"), "html.parser")
        assert soup.select_one('.kicker a[href="../../index.html"]') is not None
        assert soup.select_one('.report-breadcrumbs a[href="../../index.html"]') is not None

    map_soup = BeautifulSoup(
        (individual_dir / "map.html").read_text(encoding="utf-8"),
        "html.parser",
    )
    assert map_soup.select_one('.report-breadcrumbs a[href="index.html"]') is not None


def test_cached_translations_are_display_only_and_preserve_originals(
    tmp_path: Path,
) -> None:
    agents_dir, visit_path, observation, memory = _write_agent(tmp_path)
    _write_translations(tmp_path, observation, memory)
    before = hashlib.sha256(visit_path.read_bytes()).hexdigest()
    output_dir = tmp_path / "reports"

    generate_world_report_collection(agents_dir, output_dir, "stray-001")

    assert hashlib.sha256(visit_path.read_bytes()).hexdigest() == before
    report = (
        output_dir / "individuals" / "stray-001" / "2026-07-21_130524.html"
    ).read_text(encoding="utf-8")
    soup = BeautifulSoup(report, "html.parser")

    assert "ホストが選んだ信頼済みの受け入れ経路を進んだ。" in report
    assert "AFTERHOURS.mdを読み、作業の余像に気づいた。" in report
    assert observation in report
    assert memory in report
    assert len(soup.select("details.original-text")) == 2
    assert all(
        details.find("summary").get_text(strip=True) == "原文"
        for details in soup.select("details.original-text")
    )
