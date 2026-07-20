from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

import yaml

_JST = ZoneInfo("Asia/Tokyo")
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


class StrayError(RuntimeError):
    pass


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    drawn_to: list[str]
    avoids: list[str]
    max_places: int
    max_memories: int
    max_trace_characters: int
    may_leave_silently: bool


@dataclass(slots=True)
class State:
    status: str = "unborn"
    visit_count: int = 0
    current_location: str | None = None
    last_visit: str | None = None
    fatigue: float = 0.0
    unresolved_impulses: list[str] | None = None

    def __post_init__(self) -> None:
        self.unresolved_impulses = self.unresolved_impulses or []


def _now() -> str:
    return datetime.now(_JST).isoformat(timespec="seconds")


def _load_profile(agent_dir: Path) -> Profile:
    data = yaml.safe_load((agent_dir / "profile.yml").read_text(encoding="utf-8"))
    attention = data.get("attention", {})
    movement = data.get("movement", {})
    memory = data.get("memory", {})
    trace = data.get("trace", {})
    return Profile(
        id=str(data["id"]),
        name=str(data.get("name", data["id"])),
        drawn_to=list(attention.get("drawn_to", [])),
        avoids=list(attention.get("tends_to_avoid", [])),
        max_places=int(movement.get("max_places_per_visit", 4)),
        max_memories=int(memory.get("max_new_memories_per_visit", 3)),
        max_trace_characters=int(trace.get("max_characters", 280)),
        may_leave_silently=bool(movement.get("may_leave_silently", True)),
    )


def _load_state(agent_dir: Path) -> State:
    path = agent_dir / "state.json"
    return State(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else State()


def _save_state(agent_dir: Path, state: State) -> None:
    (agent_dir / "state.json").write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _read_page(location: Path, root: Path) -> tuple[str, str, list[tuple[str, Path]]]:
    path = location.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise StrayError(f"path escapes bounded venue: {path}") from exc
    if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
        raise StrayError(f"unreadable venue page: {path}")
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
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.lower() in _TEXT_SUFFIXES:
            links.append((label.strip()[:160], candidate))
    return title, text, links[:12]


def _term(profile: Profile, title: str, text: str) -> str | None:
    haystack = f"{title}\n{text}".lower()
    for phrase in profile.drawn_to:
        for token in re.split(r"[\s・,/]+", phrase.lower()):
            if len(token) >= 2 and token in haystack:
                return token
    defaults = ["trace", "forgotten", "unfinished", "absence", "入口", "消え", "跡", "帰"]
    return next((term for term in defaults if term in haystack), None)


def _choose(profile: Profile, links: list[tuple[str, Path]], rng: random.Random) -> Path:
    scored: list[tuple[int, Path]] = []
    for label, target in links:
        value = f"{label} {target}".lower()
        score = sum(term.lower() in value for term in profile.drawn_to)
        score -= sum(term.lower() in value for term in profile.avoids)
        scored.append((score, target))
    best = max(score for score, _ in scored)
    return rng.choice([target for score, target in scored if score == best])


def _append_memory(agent_dir: Path, items: list[str], visited_at: str) -> list[str]:
    clean = list(dict.fromkeys(" ".join(item.split()) for item in items if item.strip()))
    if not clean:
        return []
    path = agent_dir / "memory.md"
    existing = path.read_text(encoding="utf-8").rstrip() if path.exists() else "# Memory"
    path.write_text(
        existing + "\n\n## " + visited_at + "\n" + "\n".join(f"- {item}" for item in clean) + "\n",
        encoding="utf-8",
    )
    return clean


def _save_trace(outbox: Path, profile: Profile, source: Path, term: str, visited_at: str) -> Path:
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = visited_at[:19].replace(":", "").replace("T", "_")
    path = outbox / f"{stamp}_{profile.id}.md"
    trace = f"ここでは、説明よりも「{term}」の周辺が長く残った。"[: profile.max_trace_characters]
    path.write_text(
        f"---\nvisitor: {profile.id}\nvisited_at: {visited_at}\nsource: {json.dumps(str(source), ensure_ascii=False)}\nstatus: carried-home\n---\n\n{trace}\n",
        encoding="utf-8",
    )
    return path


def run_visit(*, agent_dir: Path, local_root: Path, entrance: Path, outbox: Path, seed: int | None = None) -> dict:
    profile = _load_profile(agent_dir)
    state = _load_state(agent_dir)
    rng = random.Random(seed)
    started_at = _now()
    location = entrance.resolve()
    steps: list[dict] = []
    memories: list[str] = []
    trace_file: Path | None = None
    exit_reason = "place_limit"

    for number in range(1, profile.max_places + 1):
        title, text, links = _read_page(location, local_root)
        term = _term(profile, title, text)
        if links and number < profile.max_places:
            target = _choose(profile, links, rng)
            steps.append({"step": number, "location": str(location), "title": title, "action": "follow_link", "target": str(target)})
            location = target
            state.fatigue = min(1.0, state.fatigue + 0.18)
            continue
        should_speak = bool(term) and (not profile.may_leave_silently or rng.random() >= 0.20)
        if should_speak:
            trace_file = _save_trace(outbox, profile, location, term or "something", _now())
            memories.append(f"{title}で「{term}」に立ち止まった。")
            steps.append({"step": number, "location": str(location), "title": title, "action": "leave_trace"})
            exit_reason = "trace_carried_home"
        else:
            steps.append({"step": number, "location": str(location), "title": title, "action": "leave"})
            exit_reason = "left_silently"
        break

    ended_at = _now()
    added = _append_memory(agent_dir, memories[: profile.max_memories], ended_at)
    state.status = "awake"
    state.visit_count += 1
    state.current_location = str(location)
    state.last_visit = ended_at
    state.fatigue = max(0.0, state.fatigue - 0.08)
    _save_state(agent_dir, state)

    record = {"agent_id": profile.id, "started_at": started_at, "ended_at": ended_at,
              "entrance": str(entrance.resolve()), "backend": "mock", "steps": steps,
              "trace_file": str(trace_file) if trace_file else None,
              "memories_added": added, "exit_reason": exit_reason}
    visits = agent_dir / "visits"
    visits.mkdir(parents=True, exist_ok=True)
    visit_file = visits / f"{started_at[:19].replace(':', '').replace('T', '_')}.json"
    visit_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["visit_file"] = str(visit_file)
    return record
