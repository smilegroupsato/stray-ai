from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _make_repository(repository: Path, *, missing: str | None = None) -> str:
    repository.mkdir()
    _run("git", "init", "-b", "main", cwd=repository)
    _run("git", "config", "user.email", "snapshot-test@example.invalid", cwd=repository)
    _run("git", "config", "user.name", "Snapshot Test", cwd=repository)

    files = {
        "README.md": "# GENAI-RON\n\n[History](CHAT_HISTORY.md)\n",
        "CHAT_HISTORY.md": "# Decision history\n\n[Afterhours](AFTERHOURS.md)\n",
        "AFTERHOURS.md": "# Afterhours\n",
        "CODEX.md": "# Strong implementation instructions\n",
    }
    for name, content in files.items():
        if name != missing:
            (repository / name).write_text(content, encoding="utf-8")
    site = repository / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>", encoding="utf-8")

    _run("git", "add", ".", cwd=repository)
    _run("git", "commit", "-m", "Create GENAI-RON fixture", cwd=repository)
    return _run("git", "rev-parse", "HEAD", cwd=repository).stdout.strip()


def _environment(tmp_path: Path, source: Path) -> dict[str, str]:
    return {
        **os.environ,
        "DATA_DIR": str(tmp_path / "stray-data"),
        "GENAI_RON_REPO_URL": source.as_uri(),
    }


def _make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    paths = sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True)
    for path in paths:
        if path.is_symlink():
            continue
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    root.chmod(root.stat().st_mode | stat.S_IWUSR)


def test_snapshot_copies_exact_manifest_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "web-genai-ron-jp"
    expected_commit = _make_repository(source)
    data_dir = tmp_path / "stray-data"
    script = Path(__file__).parents[1] / "scripts" / "snapshot_genai_ron_rc.sh"
    environment = _environment(tmp_path, source)

    try:
        first = subprocess.run(
            ["bash", str(script)],
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        )
        snapshot = Path(first.stdout.strip().splitlines()[-1])

        assert snapshot.name == expected_commit
        assert {path.name for path in snapshot.iterdir()} == {
            "README.md",
            "CHAT_HISTORY.md",
            "AFTERHOURS.md",
            "SNAPSHOT.txt",
        }
        assert not (snapshot / "CODEX.md").exists()
        assert not (snapshot / "site").exists()

        metadata = (snapshot / "SNAPSHOT.txt").read_text(encoding="utf-8")
        assert "venue_id=genai-ron-rc" in metadata
        assert "venue_label=GENAI-RON Repository Context" in metadata
        assert f"source_commit={expected_commit}" in metadata
        assert "manifest_count=3" in metadata
        assert "manifest_file_1=README.md" in metadata
        assert "manifest_file_2=CHAT_HISTORY.md" in metadata
        assert "manifest_file_3=AFTERHOURS.md" in metadata

        current = data_dir / "venues" / "genai-ron-rc" / "current"
        assert current.resolve() == snapshot.resolve()

        second = subprocess.run(
            ["bash", str(script)],
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        )
        assert Path(second.stdout.strip().splitlines()[-1]) == snapshot
    finally:
        _make_tree_writable(data_dir)


def test_snapshot_fails_closed_when_manifest_file_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "web-genai-ron-jp"
    _make_repository(source, missing="AFTERHOURS.md")
    script = Path(__file__).parents[1] / "scripts" / "snapshot_genai_ron_rc.sh"

    completed = subprocess.run(
        ["bash", str(script)],
        env=_environment(tmp_path, source),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "AFTERHOURS.md" in completed.stderr
    _make_tree_writable(tmp_path / "stray-data")


def test_snapshot_rejects_symlinked_manifest_file(tmp_path: Path) -> None:
    source = tmp_path / "web-genai-ron-jp"
    source.mkdir()
    _run("git", "init", "-b", "main", cwd=source)
    _run("git", "config", "user.email", "snapshot-test@example.invalid", cwd=source)
    _run("git", "config", "user.name", "Snapshot Test", cwd=source)
    (source / "README.md").write_text("# Entrance\n", encoding="utf-8")
    (source / "CHAT_HISTORY.md").write_text("# History\n", encoding="utf-8")
    (source / "outside.md").write_text("# Outside\n", encoding="utf-8")
    os.symlink("outside.md", source / "AFTERHOURS.md")
    _run("git", "add", ".", cwd=source)
    _run("git", "commit", "-m", "Create unsafe fixture", cwd=source)
    script = Path(__file__).parents[1] / "scripts" / "snapshot_genai_ron_rc.sh"

    completed = subprocess.run(
        ["bash", str(script)],
        env=_environment(tmp_path, source),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "AFTERHOURS.md" in completed.stderr
    _make_tree_writable(tmp_path / "stray-data")
