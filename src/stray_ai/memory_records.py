from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

_SCHEMA = "stray-memory-v1"
_MAX_MEMORY_CHARACTERS = 240


class MemoryRecordError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    text: str
    source_step: int | None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:_MAX_MEMORY_CHARACTERS]


def _validate_source_visit(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 2:
        raise MemoryRecordError("source_visit must be a relative visits/<file>.json path")
    if path.parts[0] != "visits" or path.suffix != ".json":
        raise MemoryRecordError("source_visit must be a relative visits/<file>.json path")
    return path.as_posix()


def _record_id(source_visit: str, ordinal: int) -> str:
    return f"{PurePosixPath(source_visit).stem}:{ordinal:02d}"


def _record(
    *,
    text: str,
    recorded_at: str,
    source_visit: str,
    source_step: int | None,
    ordinal: int,
) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "memory_id": _record_id(source_visit, ordinal),
        "text": text,
        "recorded_at": recorded_at,
        "source_visit": source_visit,
        "source_step": source_step,
        "model_authored_time": None,
    }


def load_memory_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MemoryRecordError(
                f"invalid memory record JSON at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
            raise MemoryRecordError(f"invalid memory record at {path}:{line_number}")
        required = ("memory_id", "text", "recorded_at", "source_visit")
        if any(not isinstance(value.get(key), str) or not value[key] for key in required):
            raise MemoryRecordError(f"incomplete memory record at {path}:{line_number}")
        _validate_source_visit(value["source_visit"])
        source_step = value.get("source_step")
        if source_step is not None and (
            isinstance(source_step, bool) or not isinstance(source_step, int) or source_step < 1
        ):
            raise MemoryRecordError(f"invalid source_step at {path}:{line_number}")
        records.append(value)
    return records


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    body = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def _append_markdown(path: Path, texts: list[str], recorded_at: str) -> None:
    existing = path.read_text(encoding="utf-8").rstrip() if path.exists() else "# Memory"
    body = existing + "\n\n## " + recorded_at + "\n" + "\n".join(
        f"- {text}" for text in texts
    ) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def _normalized_candidates(
    candidates: Iterable[MemoryCandidate],
    *,
    max_items: int,
) -> list[MemoryCandidate]:
    normalized: list[MemoryCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = _clean_text(candidate.text)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(MemoryCandidate(text=text, source_step=candidate.source_step))
        if len(normalized) >= max_items:
            break
    return normalized


def persist_memories(
    agent_dir: Path,
    candidates: Iterable[MemoryCandidate],
    *,
    recorded_at: str,
    source_visit: str,
    max_items: int,
) -> list[str]:
    source_visit = _validate_source_visit(source_visit)
    normalized = _normalized_candidates(candidates, max_items=max_items)
    if not normalized:
        return []

    records_path = agent_dir / "memory_records.jsonl"
    existing = load_memory_records(records_path)
    existing_by_id = {str(record["memory_id"]): record for record in existing}
    additions: list[dict[str, Any]] = []
    for ordinal, candidate in enumerate(normalized, start=1):
        record = _record(
            text=candidate.text,
            recorded_at=recorded_at,
            source_visit=source_visit,
            source_step=candidate.source_step,
            ordinal=ordinal,
        )
        prior = existing_by_id.get(record["memory_id"])
        if prior is not None:
            if prior != record:
                raise MemoryRecordError(
                    f"memory_id collision for {record['memory_id']}"
                )
            continue
        additions.append(record)

    if additions:
        _write_records(records_path, [*existing, *additions])
        _append_markdown(
            agent_dir / "memory.md",
            [candidate.text for candidate in normalized],
            recorded_at,
        )
    return [candidate.text for candidate in normalized]


def migrate_memory_records(agent_dir: Path) -> bool:
    records_path = agent_dir / "memory_records.jsonl"
    existing = load_memory_records(records_path)
    existing_ids = {str(record["memory_id"]) for record in existing}
    additions: list[dict[str, Any]] = []
    visits_dir = agent_dir / "visits"
    if not visits_dir.is_dir():
        return False

    for visit_path in sorted(visits_dir.glob("*.json")):
        try:
            visit = json.loads(visit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(visit, dict):
            continue
        recorded_at = visit.get("ended_at") or visit.get("started_at")
        memories = visit.get("memories_added")
        if not isinstance(recorded_at, str) or not recorded_at:
            continue
        if not isinstance(memories, list):
            continue
        source_visit = f"visits/{visit_path.name}"
        for ordinal, item in enumerate(memories, start=1):
            text = _clean_text(item)
            if not text:
                continue
            record = _record(
                text=text,
                recorded_at=recorded_at,
                source_visit=source_visit,
                source_step=None,
                ordinal=ordinal,
            )
            if record["memory_id"] in existing_ids:
                continue
            existing_ids.add(str(record["memory_id"]))
            additions.append(record)

    if not additions:
        return False
    _write_records(records_path, [*existing, *additions])
    return True
