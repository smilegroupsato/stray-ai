from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


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


def load_profile(agent_dir: Path) -> Profile:
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


def load_state(agent_dir: Path) -> State:
    path = agent_dir / "state.json"
    return State(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else State()


def save_state(agent_dir: Path, state: State) -> None:
    (agent_dir / "state.json").write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
