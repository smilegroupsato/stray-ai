from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "devbox" / "birth-stray-002-v0.sh"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _persistent_primary(data_dir: Path) -> Path:
    primary = data_dir / "agents" / "stray-001"
    primary.mkdir(parents=True)
    (primary / "profile.yml").write_text("id: stray-001\nname: unchanged\n")
    (primary / "memory.md").write_text("# Memory\n\nPRIMARY-MEMORY\n")
    (primary / "state.json").write_text(
        '{"status":"resting","visit_count":5}\n',
        encoding="utf-8",
    )
    return primary


def _run(data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "REPO_DIR": str(REPO_ROOT),
        "DATA_DIR": str(data_dir),
        "PYTHON_BIN": sys.executable,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_birth_creates_one_isolated_persistent_individual(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    primary = _persistent_primary(data_dir)
    before = {
        name: _digest(primary / name)
        for name in ("profile.yml", "memory.md", "state.json")
    }

    result = _run(data_dir)

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["born"] is True
    assert output["agent_id"] == "stray-002"
    assert output["status"] == "resting"
    assert output["visit_count"] == 0
    assert output["document_rummage_count"] == 1
    assert output["primary_individual"] == "stray-001"
    assert output["primary_unchanged"] is True
    assert output["wake_invoked"] is False
    assert output["visit_invoked"] is False
    assert output["scheduler_created"] is False
    assert output["report_published"] is False

    born = data_dir / "agents" / "stray-002"
    assert {
        path.name for path in born.iterdir()
    } == {
        "birth.json",
        "memory.md",
        "observation-log.md",
        "profile.yml",
        "rummages",
        "state.json",
        "visit_requests",
        "visits",
        "wake_checks",
        "wake_selections",
    }
    for directory in (
        "rummages",
        "visit_requests",
        "visits",
        "wake_checks",
        "wake_selections",
    ):
        assert (born / directory).is_dir()
        assert list((born / directory).iterdir()) == []

    manifest = json.loads((born / "birth.json").read_text(encoding="utf-8"))
    state = json.loads((born / "state.json").read_text(encoding="utf-8"))
    assert state["runtime_rummage_count"] == 0
    assert state["llm_rummage_count"] == 0
    assert manifest["schema"] == "stray-persistent-birth-v0"
    assert manifest["agent_id"] == "stray-002"
    assert manifest["source_commit"]
    assert manifest["effects"] == {
        "wake_invoked": False,
        "visit_invoked": False,
        "scheduler_created": False,
        "report_published": False,
    }
    for name, digest in manifest["template_sha256"].items():
        assert digest == _digest(born / name)

    after = {
        name: _digest(primary / name)
        for name in ("profile.yml", "memory.md", "state.json")
    }
    assert after == before


def test_birth_refuses_to_overwrite_existing_stray_002(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _persistent_primary(data_dir)

    first = _run(data_dir)
    assert first.returncode == 0, first.stderr
    born = data_dir / "agents" / "stray-002"
    protected = {
        path.relative_to(born).as_posix(): _digest(path)
        for path in born.rglob("*")
        if path.is_file()
    }

    second = _run(data_dir)

    assert second.returncode != 0
    assert "already exists; refusing to overwrite" in second.stderr
    assert {
        path.relative_to(born).as_posix(): _digest(path)
        for path in born.rglob("*")
        if path.is_file()
    } == protected
