from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def source_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_report_translations(path: Path | None) -> dict[str, str]:
    """Load exact-source Japanese translations without mutating Visit records.

    Invalid, stale, or hash-mismatched entries fail closed and are ignored.
    """

    if path is None or not path.is_file():
        return {}
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict) or value.get("version") != 1:
        return {}

    entries = value.get("translations")
    if not isinstance(entries, list):
        return {}

    translations: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        translated = entry.get("translation")
        digest = entry.get("source_sha256")
        if not isinstance(source, str) or not source.strip():
            continue
        if not isinstance(translated, str) or not translated.strip():
            continue
        if not isinstance(digest, str) or digest != source_digest(source):
            continue
        translations[source] = translated.strip()
    return translations
