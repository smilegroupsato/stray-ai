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


def _make_public_venue(repository: Path) -> str:
    repository.mkdir()
    _run("git", "init", "-b", "main", cwd=repository)
    _run("git", "config", "user.email", "snapshot-test@example.invalid", cwd=repository)
    _run("git", "config", "user.name", "Snapshot Test", cwd=repository)

    (repository / "docs").mkdir()
    (repository / "flyer").mkdir()
    (repository / "README.md").write_text(
        "# Entrance\n\n[Map](REPOSITORY_CONTEXT.md)\n", encoding="utf-8"
    )
    (repository / "REPOSITORY_CONTEXT.md").write_text(
        "# Map\n\n[Reception](AGENTS.md)\n", encoding="utf-8"
    )
    (repository / "AGENTS.md").write_text("# Reception\n", encoding="utf-8")
    (repository / "docs" / "concept.md").write_text("# Concept\n", encoding="utf-8")
    (repository / "flyer" / "index.html").write_text("<html></html>", encoding="utf-8")
    (repository / "private.bin").write_bytes(b"not venue text")
    os.symlink("README.md", repository / "linked-entrance.md")

    _run("git", "add", ".", cwd=repository)
    _run("git", "commit", "-m", "Create test venue", cwd=repository)
    return _run("git", "rev-parse", "HEAD", cwd=repository).stdout.strip()


def _make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode | stat.S_IWUSR, follow_symlinks=False)
    root.chmod(root.stat().st_mode | stat.S_IWUSR)


def test_snapshot_copies_only_bounded_text(tmp_path: Path) -> None:
    source_repository = tmp_path / "public-venue"
    expected_commit = _make_public_venue(source_repository)
    data_dir = tmp_path / "stray-data"
    script = Path(__file__).parents[1] / "scripts" / "snapshot_eternal_free_party.sh"
    repository_url = source_repository.as_uri()
    environment = {
        **os.environ,
        "DATA_DIR": str(data_dir),
        "EFP_REPO_URL": repository_url,
    }

    try:
        first = subprocess.run(
            ["bash", str(script)],
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        )
        snapshot = Path(first.stdout.strip())

        assert snapshot.name == expected_commit
        assert (snapshot / "README.md").is_file()
        assert (snapshot / "REPOSITORY_CONTEXT.md").is_file()
        assert (snapshot / "AGENTS.md").is_file()
        assert (snapshot / "docs" / "concept.md").is_file()
        assert not (snapshot / "flyer" / "index.html").exists()
        assert not (snapshot / "private.bin").exists()
        assert not (snapshot / "linked-entrance.md").exists()
        assert (snapshot / "SNAPSHOT.txt").read_text(encoding="utf-8").find(
            f"source_commit={expected_commit}"
        ) >= 0

        current = data_dir / "venues" / "eternal-free-party" / "current"
        assert current.resolve() == snapshot.resolve()

        second = subprocess.run(
            ["bash", str(script)],
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        )
        assert Path(second.stdout.strip()) == snapshot
    finally:
        _make_tree_writable(data_dir)
