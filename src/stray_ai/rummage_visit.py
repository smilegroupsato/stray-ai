from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


class RummageVisitError(RuntimeError):
    pass


def _text(value: Any, *, default: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text or default


def _safe_relative_path(value: Any) -> str:
    path = PurePosixPath(str(value or ""))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise RummageVisitError("rummage document path must be repository-relative")
    return path.as_posix()


def _stamp(started_at: Any) -> str:
    try:
        value = datetime.fromisoformat(str(started_at))
    except ValueError as exc:
        raise RummageVisitError("rummage started_at must be ISO-8601") from exc
    return value.strftime("%Y-%m-%d_%H%M%S")


def visit_filename_for_rummage(record: dict[str, Any]) -> str:
    return f"{_stamp(record.get('started_at'))}.json"


def rummage_to_visit(
    record: dict[str, Any],
    *,
    rummage_record: str,
) -> dict[str, Any]:
    if record.get("schema") != "stray-rummage-v1":
        raise RummageVisitError("unsupported rummage schema")
    agent_id = _text(record.get("agent_id"))
    if not agent_id:
        raise RummageVisitError("rummage agent_id is required")
    repository = record.get("repository")
    if not isinstance(repository, dict):
        raise RummageVisitError("rummage repository is required")
    repository_name = _text(repository.get("name"))
    if not repository_name:
        raise RummageVisitError("rummage repository name is required")
    documents = record.get("documents")
    if not isinstance(documents, list) or not documents:
        raise RummageVisitError("rummage documents are required")

    steps: list[dict[str, Any]] = []
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            raise RummageVisitError("rummage document must be an object")
        location = _safe_relative_path(document.get("path"))
        mode = _text(document.get("reading_mode"), default="cover-skimming")
        step = {
            "step": index,
            "location": location,
            "title": _text(document.get("title"), default=PurePosixPath(location).stem),
            "action": "deep_read" if mode == "deep-reading" else "skim_cover",
            "reading_mode": mode,
        }
        observation = document.get("deep_reading")
        if isinstance(observation, dict):
            step["observation"] = {
                "local_law": _text(observation.get("local_law")),
                "residue": _text(observation.get("residue")),
            }
        cover_note = _text(document.get("cover_note"))
        if cover_note:
            step["cover_note"] = cover_note
        steps.append(step)

    steps[-1]["return"] = "damp-underground-library-shelf-gap"
    trace = _text(record.get("trace"))
    return {
        "schema": "stray-visit-v1",
        "agent_id": agent_id,
        "activity_type": "document_rummage",
        "started_at": record.get("started_at"),
        "ended_at": record.get("ended_at") or record.get("started_at"),
        "venue": {
            "kind": "repository",
            "id": f"repository:{repository_name}",
            "label": repository_name,
            "source_commit": repository.get("source_commit"),
        },
        "entrance": steps[0]["location"],
        "backend": record.get("backend") or "unknown",
        "brain_model": record.get("brain_model"),
        "steps": steps,
        "memories_added": list(record.get("memories_added") or []),
        "trace": trace or None,
        "trace_file": None,
        "exit_reason": "returned_after_document_rummage",
        "rummage_record": rummage_record,
        "effects": {
            "repository_content_changed": False,
            "external_write": False,
            "returned_to_rest": True,
        },
    }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RummageVisitError(f"record is not readable: {path.name}") from exc
    if not isinstance(value, dict):
        raise RummageVisitError(f"record is not an object: {path.name}")
    return value


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise RummageVisitError(f"Visit record already exists: {path.name}")
        os.link(temporary, path)
        temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)


def _latest_visit(visits_dir: Path) -> dict[str, Any] | None:
    records: list[dict[str, Any]] = []
    for path in sorted(visits_dir.glob("*.json")):
        try:
            value = _load_object(path)
        except RummageVisitError:
            continue
        records.append(value)
    return max(records, key=lambda item: str(item.get("started_at") or "")) if records else None


def _refresh_state(agent_dir: Path) -> bool:
    state_path = agent_dir / "state.json"
    state = _load_object(state_path)
    visits = [
        _load_object(path)
        for path in sorted((agent_dir / "visits").glob("*.json"))
        if path.is_file() and not path.is_symlink()
    ]
    original = json.dumps(state, ensure_ascii=False, sort_keys=True)
    latest = _latest_visit(agent_dir / "visits")
    state["visit_count"] = max(
        int(state.get("visit_count", 0) or 0),
        len(visits),
    )
    state["llm_visit_count"] = max(
        int(state.get("llm_visit_count", 0) or 0),
        sum(record.get("backend") == "command" for record in visits),
    )
    state["rummage_visit_count"] = sum(
        record.get("activity_type") == "document_rummage" for record in visits
    )
    if latest is not None and str(
        latest.get("ended_at") or latest.get("started_at") or ""
    ) >= str(state.get("last_visit") or ""):
        state["last_visit"] = latest.get("ended_at") or latest.get("started_at")
        state["last_exit_reason"] = latest.get("exit_reason")
        state["last_backend"] = latest.get("backend")
        state["last_model"] = latest.get("brain_model")
    updated = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if updated == original:
        return False
    temporary = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, state_path)
    return True


def migrate_rummage_visits(
    agent_dir: Path,
    *,
    seed_visit: Path | None = None,
) -> dict[str, Any]:
    if not agent_dir.is_dir() or agent_dir.is_symlink():
        raise RummageVisitError("agent directory must be an existing non-symlink directory")
    rummages_dir = agent_dir / "rummages"
    visits_dir = agent_dir / "visits"
    for directory in (rummages_dir, visits_dir):
        if not directory.is_dir() or directory.is_symlink():
            raise RummageVisitError(
                f"{directory.name} directory must exist and must not be a symlink"
            )

    created: list[str] = []
    if seed_visit is not None:
        if not seed_visit.is_file() or seed_visit.is_symlink():
            raise RummageVisitError("seed Visit must be a safe ordinary file")
        seed = _load_object(seed_visit)
        seed_name = seed_visit.name
        target = visits_dir / seed_name
        if target.exists():
            if _load_object(target) != seed:
                raise RummageVisitError(
                    f"existing Visit conflicts with seed: {seed_name}"
                )
        else:
            _write_new_json(target, seed)
            created.append(seed_name)

    for rummage_path in sorted(rummages_dir.glob("*.json")):
        if rummage_path.is_symlink():
            raise RummageVisitError(
                f"rummage record must not be a symlink: {rummage_path.name}"
            )
        record = _load_object(rummage_path)
        visit_name = visit_filename_for_rummage(record)
        visit_path = visits_dir / visit_name
        expected = rummage_to_visit(
            record,
            rummage_record=f"rummages/{rummage_path.name}",
        )
        if visit_path.exists():
            existing = _load_object(visit_path)
            if (
                existing.get("activity_type") != "document_rummage"
                or existing.get("rummage_record") != expected["rummage_record"]
            ):
                raise RummageVisitError(
                    f"existing Visit conflicts with rummage: {visit_name}"
                )
            continue
        _write_new_json(visit_path, expected)
        created.append(visit_name)

    return {
        "created_visit_files": created,
        "created_visit_count": len(created),
        "state_changed": _refresh_state(agent_dir),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="stray-ai-migrate-rummage-visits")
    parser.add_argument("agent_dir", type=Path)
    parser.add_argument("--seed-visit", type=Path)
    args = parser.parse_args()
    result = migrate_rummage_visits(
        args.agent_dir.resolve(),
        seed_visit=args.seed_visit.resolve() if args.seed_visit else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
