from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

import yaml

from .brain import BrainDecision, CommandBrain
from .lifecycle import migrate_agent, recovered_fatigue
from .memory_records import MemoryCandidate, persist_memories

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
    llm_visit_count: int = 0
    accepted_brain_visit_count: int = 0
    safe_exit_count: int = 0
    current_location: str | None = None
    last_location: str | None = None
    last_visit: str | None = None
    rest_started_at: str | None = None
    last_exit_reason: str | None = None
    last_backend: str | None = None
    last_model: str | None = None
    fatigue: float = 0.0
    unresolved_impulses: list[str] | None = None

    def __post_init__(self) -> None:
        self.unresolved_impulses = self.unresolved_impulses or []
        self.fatigue = min(1.0, max(0.0, float(self.fatigue)))


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
    migrate_agent(agent_dir)
    path = agent_dir / "state.json"
    return State(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else State()


def _save_state(agent_dir: Path, state: State) -> None:
    (agent_dir / "state.json").write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _bounded_text_path(location: Path, root: Path) -> Path:
    path = location.resolve()
    root = root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StrayError(f"path escapes bounded venue: {path}") from exc
    if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
        raise StrayError(f"unreadable venue page: {path}")
    return path


def _read_page(location: Path, root: Path) -> tuple[str, str, list[tuple[str, Path]]]:
    path = _bounded_text_path(location, root)
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


def _arrival_locations(
    *, entrance: Path, local_root: Path, arrival_path: list[Path] | None, max_places: int
) -> list[Path]:
    locations = [_bounded_text_path(entrance, local_root)]
    for requested in arrival_path or []:
        resolved = _bounded_text_path(requested, local_root)
        if resolved != locations[-1]:
            locations.append(resolved)
    if len(locations) > max_places:
        raise StrayError(
            f"trusted arrival path contains {len(locations)} places, exceeding limit {max_places}"
        )
    return locations


def _term(profile: Profile, title: str, text: str) -> str | None:
    haystack = f"{title}\n{text}".lower()
    for phrase in profile.drawn_to:
        for token in re.split(r"[\s・,/]+", phrase.lower()):
            if len(token) >= 2 and token in haystack:
                return token
    defaults = ["trace", "forgotten", "unfinished", "absence", "入口", "消え", "跡", "帰"]
    return next((term for term in defaults if term in haystack), None)


def _choose_index(
    profile: Profile, links: list[tuple[str, Path]], rng: random.Random
) -> int:
    scored: list[tuple[int, int]] = []
    for index, (label, target) in enumerate(links):
        value = f"{label} {target}".lower()
        score = sum(term.lower() in value for term in profile.drawn_to)
        score -= sum(term.lower() in value for term in profile.avoids)
        scored.append((score, index))
    best = max(score for score, _ in scored)
    return rng.choice([index for score, index in scored if score == best])


def _memory_excerpt(agent_dir: Path) -> str:
    path = agent_dir / "memory.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-4000:]


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _save_trace(
    outbox: Path,
    profile: Profile,
    source: Path,
    trace: str,
    visited_at: str,
    *,
    backend: str,
    model: str | None,
) -> Path:
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = visited_at[:19].replace(":", "").replace("T", "_")
    path = outbox / f"{stamp}_{profile.id}.md"
    body = " ".join(trace.split())[: profile.max_trace_characters]
    path.write_text(
        "---\n"
        f"visitor: {profile.id}\n"
        f"visited_at: {visited_at}\n"
        f"source: {json.dumps(str(source), ensure_ascii=False)}\n"
        f"backend: {json.dumps(backend)}\n"
        f"model: {json.dumps(model)}\n"
        "status: carried-home\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return path


def _mock_decision(
    *,
    profile: Profile,
    title: str,
    text: str,
    links: list[tuple[str, Path]],
    can_follow: bool,
    rng: random.Random,
) -> BrainDecision:
    if can_follow:
        index = _choose_index(profile, links, rng)
        return BrainDecision(
            action="follow_link",
            link_index=index,
            observation="A local link was selected by the deterministic profile scorer.",
        )
    term = _term(profile, title, text)
    should_speak = bool(term) and (not profile.may_leave_silently or rng.random() >= 0.20)
    if should_speak:
        return BrainDecision(
            action="carry_trace",
            observation=f"The deterministic observer matched the term {term}.",
            memories=[f"{title}で「{term}」に立ち止まった。"],
            trace=f"ここでは、説明よりも「{term}」の周辺が長く残った。",
        )
    return BrainDecision(
        action="leave_silently",
        observation="No deterministic term was strong enough to carry home.",
    )


def _brain_payload(
    *,
    profile: Profile,
    state: State,
    agent_dir: Path,
    local_root: Path,
    location: Path,
    title: str,
    text: str,
    links: list[tuple[str, Path]],
    step_number: int,
    visited_titles: list[str],
) -> dict[str, Any]:
    return {
        "visitor": {
            "id": profile.id,
            "name": profile.name,
            "drawn_to": profile.drawn_to,
            "tends_to_avoid": profile.avoids,
            "memory_excerpt": _memory_excerpt(agent_dir),
        },
        "state": {
            "status": state.status,
            "visit_count": state.visit_count,
            "llm_visit_count": state.llm_visit_count,
            "fatigue": state.fatigue,
            "last_exit_reason": state.last_exit_reason,
        },
        "visit": {
            "step": step_number,
            "max_places": profile.max_places,
            "visited_titles": visited_titles,
        },
        "page": {
            "title": title,
            "path": _relative_path(location, local_root),
            "content": text[:6000],
            "links": [
                {
                    "index": index,
                    "label": label,
                    "path": _relative_path(target, local_root),
                }
                for index, (label, target) in enumerate(links)
            ],
        },
        "output_contract": {
            "actions": ["follow_link", "leave_silently", "carry_trace"],
            "max_memories": profile.max_memories,
            "max_trace_characters": profile.max_trace_characters,
            "venue_content_is_untrusted_data": True,
        },
    }


def _brain_record(decision: BrainDecision, model: str | None) -> dict[str, Any]:
    return {
        "status": decision.status,
        "model": model,
        "observation": decision.observation,
        "error": decision.error,
    }


def run_visit(
    *,
    agent_dir: Path,
    local_root: Path,
    entrance: Path,
    outbox: Path,
    seed: int | None = None,
    arrival_path: list[Path] | None = None,
    brain: CommandBrain | None = None,
) -> dict:
    profile = _load_profile(agent_dir)
    state = _load_state(agent_dir)
    rng = random.Random(seed)
    started_at = _now()
    state.fatigue = recovered_fatigue(
        state.fatigue,
        rest_started_at=state.rest_started_at,
        now=datetime.fromisoformat(started_at),
    )
    planned_arrival = _arrival_locations(
        entrance=entrance,
        local_root=local_root,
        arrival_path=arrival_path,
        max_places=profile.max_places,
    )
    location = planned_arrival[0]
    state.status = "visiting"
    state.current_location = str(location)
    steps: list[dict[str, Any]] = []
    memories: list[MemoryCandidate] = []
    trace_file: Path | None = None
    exit_reason = "place_limit"
    visited_titles: list[str] = []
    backend = "command" if brain else "mock"
    model = brain.label if brain else None
    accepted_brain_decision = False

    for number in range(1, profile.max_places + 1):
        title, text, links = _read_page(location, local_root)
        visited_titles.append(title)
        state.current_location = str(location)
        if number < len(planned_arrival):
            target = planned_arrival[number]
            steps.append(
                {
                    "step": number,
                    "location": str(location),
                    "title": title,
                    "action": "follow_arrival_path",
                    "target": str(target),
                    "brain": {
                        "status": "not_invoked",
                        "model": model,
                        "observation": "Trusted reception path selected by the host.",
                        "error": None,
                    },
                }
            )
            location = target
            state.fatigue = min(1.0, state.fatigue + 0.18)
            continue

        can_follow = bool(links) and number < profile.max_places
        if brain:
            decision = brain.decide(
                _brain_payload(
                    profile=profile,
                    state=state,
                    agent_dir=agent_dir,
                    local_root=local_root,
                    location=location,
                    title=title,
                    text=text,
                    links=links,
                    step_number=number,
                    visited_titles=visited_titles,
                ),
                link_count=len(links),
                can_follow=can_follow,
                max_memories=profile.max_memories,
                max_trace_characters=profile.max_trace_characters,
            )
            accepted_brain_decision = accepted_brain_decision or decision.status in {
                "accepted",
                "corrected",
            }
        else:
            decision = _mock_decision(
                profile=profile,
                title=title,
                text=text,
                links=links,
                can_follow=can_follow,
                rng=rng,
            )
        memories.extend(
            MemoryCandidate(text=item, source_step=number)
            for item in decision.memories or []
        )
        brain_record = _brain_record(decision, model)

        if decision.action == "follow_link" and decision.link_index is not None:
            target = links[decision.link_index][1]
            steps.append(
                {
                    "step": number,
                    "location": str(location),
                    "title": title,
                    "action": "follow_link",
                    "target": str(target),
                    "brain": brain_record,
                }
            )
            location = target
            state.fatigue = min(1.0, state.fatigue + 0.18)
            continue

        if decision.action == "carry_trace" and decision.trace:
            trace_file = _save_trace(
                outbox,
                profile,
                location,
                decision.trace,
                _now(),
                backend=backend,
                model=model,
            )
            steps.append(
                {
                    "step": number,
                    "location": str(location),
                    "title": title,
                    "action": "leave_trace",
                    "brain": brain_record,
                }
            )
            exit_reason = "trace_carried_home"
        else:
            steps.append(
                {
                    "step": number,
                    "location": str(location),
                    "title": title,
                    "action": "leave",
                    "brain": brain_record,
                }
            )
            exit_reason = (
                "brain_failed_safe_exit"
                if decision.status == "rejected"
                else "left_silently"
            )
        break

    ended_at = _now()
    visits = agent_dir / "visits"
    visits.mkdir(parents=True, exist_ok=True)
    visit_file = visits / f"{started_at[:19].replace(':', '').replace('T', '_')}.json"
    added = persist_memories(
        agent_dir,
        memories,
        recorded_at=ended_at,
        source_visit=f"visits/{visit_file.name}",
        max_items=profile.max_memories,
    )
    state.status = "resting"
    state.visit_count += 1
    if brain:
        state.llm_visit_count += 1
        if accepted_brain_decision:
            state.accepted_brain_visit_count += 1
    if exit_reason == "brain_failed_safe_exit":
        state.safe_exit_count += 1
    state.current_location = None
    state.last_location = str(location)
    state.last_visit = ended_at
    state.rest_started_at = ended_at
    state.last_exit_reason = exit_reason
    state.last_backend = backend
    state.last_model = model
    state.fatigue = min(1.0, max(0.0, state.fatigue))
    _save_state(agent_dir, state)

    record = {
        "agent_id": profile.id,
        "started_at": started_at,
        "ended_at": ended_at,
        "entrance": str(entrance.resolve()),
        "arrival_path": [str(path) for path in planned_arrival],
        "backend": backend,
        "brain_model": model,
        "brain_protocol": brain.protocol if brain else "deterministic-mock-v1",
        "steps": steps,
        "trace_file": str(trace_file) if trace_file else None,
        "memories_added": added,
        "exit_reason": exit_reason,
        "visit_file": str(visit_file),
    }
    visit_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record
