from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


class ReaderError(RuntimeError):
    pass


def read_page(location: Path, root: Path) -> tuple[str, str, list[tuple[str, Path]]]:
    path = location.resolve()
    root = root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReaderError(f"path escapes bounded venue: {path}") from exc
    if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
        raise ReaderError(f"unreadable venue page: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")[:9000]
    heading = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = heading.group(1).strip() if heading else path.stem
    links: list[tuple[str, Path]] = []

    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        target = target.strip().split(" ", 1)[0].strip("<>")
        parsed = urlparse(target)
        if parsed.scheme or target.startswith("#"):
            continue
        candidate = (path.parent / unquote(parsed.path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.lower() in _TEXT_SUFFIXES:
            links.append((label.strip()[:160], candidate))

    return title, text, links[:12]
