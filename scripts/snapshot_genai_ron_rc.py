from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

VENUE_ID = "genai-ron-rc"
VENUE_LABEL = "GENAI-RON Repository Context"
DEFAULT_REPOSITORY = "https://github.com/smilegroupsato/web-genai-ron-jp.git"
MANIFEST = ("README.md", "CHAT_HISTORY.md", "AFTERHOURS.md")


def _run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout.strip() if capture else ""


def _metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def _validate_snapshot(
    root: Path,
    *,
    repository: str,
    branch: str,
    commit: str,
    max_file_bytes: int,
) -> None:
    expected = {*MANIFEST, "SNAPSHOT.txt"}
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError(f"invalid snapshot directory: {root}")

    entries = {path.name for path in root.iterdir()}
    if entries != expected:
        raise RuntimeError(
            "snapshot entries differ from manifest: "
            f"expected={sorted(expected)} actual={sorted(entries)}"
        )

    for name in MANIFEST:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"invalid manifest file: {path}")
        if path.stat().st_size > max_file_bytes:
            raise RuntimeError(f"manifest file exceeds limit: {name}")

    metadata_path = root / "SNAPSHOT.txt"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise RuntimeError("invalid SNAPSHOT.txt")
    metadata = _metadata(metadata_path)
    required = {
        "venue_id": VENUE_ID,
        "venue_label": VENUE_LABEL,
        "source_repository": repository,
        "source_branch": branch,
        "source_commit": commit,
        "manifest_count": str(len(MANIFEST)),
    }
    for key, expected_value in required.items():
        if metadata.get(key) != expected_value:
            raise RuntimeError(f"snapshot metadata mismatch for {key}")
    for index, name in enumerate(MANIFEST, start=1):
        if metadata.get(f"manifest_file_{index}") != name:
            raise RuntimeError(f"snapshot manifest metadata mismatch at {index}")


def _copy_manifest(source: Path, target: Path, max_file_bytes: int) -> None:
    for raw in MANIFEST:
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise RuntimeError(f"unsafe manifest path: {raw}")
        origin = source / raw
        if origin.is_symlink() or not origin.is_file():
            raise RuntimeError(f"required manifest file missing or unsafe: {raw}")
        if origin.stat().st_size > max_file_bytes:
            raise RuntimeError(f"manifest file exceeds limit: {raw}")
        shutil.copy2(origin, target / raw)


def _make_read_only(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    root.chmod(root.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def main() -> int:
    data_dir = Path(os.environ.get("DATA_DIR", "/srv/sgos/data/stray-ai"))
    repository = os.environ.get("GENAI_RON_REPO_URL", DEFAULT_REPOSITORY)
    branch = os.environ.get("GENAI_RON_BRANCH", "main")
    source_dir = Path(
        os.environ.get(
            "GENAI_RON_SOURCE_DIR",
            str(data_dir / "sources" / VENUE_ID / "web-genai-ron-jp"),
        )
    )
    snapshot_base = Path(
        os.environ.get(
            "GENAI_RON_SNAPSHOT_BASE",
            str(data_dir / "venues" / VENUE_ID),
        )
    )
    max_file_bytes = int(os.environ.get("GENAI_RON_MAX_FILE_BYTES", "524288"))

    if not repository or "\n" in repository or not branch or "\n" in branch:
        raise RuntimeError("repository URL and branch must be single-line values")
    if max_file_bytes <= 0:
        raise RuntimeError("GENAI_RON_MAX_FILE_BYTES must be positive")

    source_dir.parent.mkdir(parents=True, exist_ok=True)
    snapshot_base.mkdir(parents=True, exist_ok=True)

    if not (source_dir / ".git").is_dir():
        _run(
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-tags",
            "--branch",
            branch,
            repository,
            str(source_dir),
        )
    else:
        actual_repository = _run(
            "git", "remote", "get-url", "origin", cwd=source_dir, capture=True
        )
        if actual_repository != repository:
            raise RuntimeError(
                f"refusing to update unexpected source remote: {actual_repository}"
            )
        if _run("git", "status", "--porcelain", cwd=source_dir, capture=True):
            raise RuntimeError(f"refusing to update a dirty source checkout: {source_dir}")
        _run("git", "fetch", "--depth", "1", "--no-tags", "origin", branch, cwd=source_dir)
        _run("git", "checkout", "--detach", "FETCH_HEAD", cwd=source_dir)

    commit = _run("git", "rev-parse", "HEAD", cwd=source_dir, capture=True)
    snapshot_dir = snapshot_base / commit

    if snapshot_dir.exists():
        _validate_snapshot(
            snapshot_dir,
            repository=repository,
            branch=branch,
            commit=commit,
            max_file_bytes=max_file_bytes,
        )
    else:
        temporary = snapshot_base / f".tmp-{commit}-{os.getpid()}"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        try:
            _copy_manifest(source_dir.resolve(), temporary.resolve(), max_file_bytes)
            captured_at = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
            lines = [
                f"venue_id={VENUE_ID}",
                f"venue_label={VENUE_LABEL}",
                f"source_repository={repository}",
                f"source_branch={branch}",
                f"source_commit={commit}",
                f"captured_at={captured_at}",
                f"manifest_count={len(MANIFEST)}",
            ]
            lines.extend(
                f"manifest_file_{index}={name}"
                for index, name in enumerate(MANIFEST, start=1)
            )
            lines.append(f"max_file_bytes={max_file_bytes}")
            (temporary / "SNAPSHOT.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            _validate_snapshot(
                temporary,
                repository=repository,
                branch=branch,
                commit=commit,
                max_file_bytes=max_file_bytes,
            )
            _make_read_only(temporary)
            temporary.rename(snapshot_dir)
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

    current_new = snapshot_base / ".current-new"
    current = snapshot_base / "current"
    current_new.unlink(missing_ok=True)
    current_new.symlink_to(commit)
    current_new.replace(current)
    print(snapshot_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
