from __future__ import annotations

import os
import subprocess
from pathlib import Path


_COMMIT = "a" * 40
_REPOSITORY = "https://github.com/smilegroupsato/web-genai-ron-jp.git"


def _snapshot(data_dir: Path, *, unexpected: bool = False) -> Path:
    root = data_dir / "venues" / "genai-ron-rc" / _COMMIT
    root.mkdir(parents=True)
    for name in ("README.md", "CHAT_HISTORY.md", "AFTERHOURS.md"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "SNAPSHOT.txt").write_text(
        "\n".join(
            [
                "venue_id=genai-ron-rc",
                "venue_label=GENAI-RON Repository Context",
                f"source_repository={_REPOSITORY}",
                "source_branch=main",
                f"source_commit={_COMMIT}",
                "manifest_count=3",
                "manifest_file_1=README.md",
                "manifest_file_2=CHAT_HISTORY.md",
                "manifest_file_3=AFTERHOURS.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if unexpected:
        (root / "CODEX.md").write_text("# Instructions\n", encoding="utf-8")
    current = root.parent / "current"
    current.symlink_to(_COMMIT)
    return root


def _launcher() -> Path:
    return Path(__file__).parents[1] / "scripts" / "visit_genai_ron_rc.sh"


def _isolated_env(data_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "STRAY_GENAI_RON_SNAPSHOT_DIR",
        "GENAI_RON_SNAPSHOT_BASE",
        "GENAI_RON_REPO_URL",
    ):
        env.pop(name, None)
    env["DATA_DIR"] = str(data_dir)
    return env


def test_launcher_uses_existing_snapshot_and_fixed_arrival_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    snapshot = _snapshot(data_dir)
    runner = data_dir / "run-first-visitor.sh"
    runner.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'root=%s\\n' \"$STRAY_LOCAL_ROOT\"\n"
        "printf 'entrance=%s\\n' \"$STRAY_ENTRANCE\"\n"
        "printf 'args=%s\\n' \"$*\"\n",
        encoding="utf-8",
    )
    runner.chmod(0o750)

    completed = subprocess.run(
        ["bash", str(_launcher()), "--max-steps", "5"],
        env=_isolated_env(data_dir),
        check=True,
        text=True,
        capture_output=True,
    )

    assert f"root={snapshot}" in completed.stdout
    assert f"entrance={snapshot / 'README.md'}" in completed.stdout
    assert (
        "args=--arrival-path CHAT_HISTORY.md AFTERHOURS.md --max-steps 5"
        in completed.stdout
    )
    assert not (data_dir / "sources").exists()


def test_launcher_fails_without_a_separately_created_snapshot(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    completed = subprocess.run(
        ["bash", str(_launcher())],
        env=_isolated_env(data_dir),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "Create and inspect one separately" in completed.stderr


def test_launcher_rejects_snapshot_outside_manifest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _snapshot(data_dir, unexpected=True)
    runner = data_dir / "run-first-visitor.sh"
    runner.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    runner.chmod(0o750)

    completed = subprocess.run(
        ["bash", str(_launcher())],
        env=_isolated_env(data_dir),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "outside the approved manifest" in completed.stderr
