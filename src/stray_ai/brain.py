from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

_ALLOWED_ACTIONS = {"follow_link", "leave_silently", "carry_trace"}
_MAX_OBSERVATION_CHARACTERS = 360
_MAX_MEMORY_CHARACTERS = 240


@dataclass(slots=True)
class BrainDecision:
    action: str
    link_index: int | None = None
    observation: str = ""
    memories: list[str] | None = None
    trace: str | None = None
    status: str = "accepted"
    error: str | None = None

    def __post_init__(self) -> None:
        self.memories = self.memories or []


def _clean_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def safe_failure(reason: str) -> BrainDecision:
    return BrainDecision(
        action="leave_silently",
        observation="The observation layer was unavailable, so the visitor left safely.",
        status="rejected",
        error=_clean_text(reason, 240),
    )


def normalize_decision(
    raw: Any,
    *,
    link_count: int,
    can_follow: bool,
    max_memories: int,
    max_trace_characters: int,
) -> BrainDecision:
    if not isinstance(raw, dict):
        return safe_failure("brain response was not a JSON object")

    action = str(raw.get("action", "")).strip()
    if action not in _ALLOWED_ACTIONS:
        return safe_failure("brain response used an unsupported action")

    observation = _clean_text(raw.get("observation"), _MAX_OBSERVATION_CHARACTERS)
    raw_memories = raw.get("memories", [])
    if not isinstance(raw_memories, list):
        raw_memories = []
    memories = []
    for item in raw_memories:
        clean = _clean_text(item, _MAX_MEMORY_CHARACTERS)
        if clean and clean not in memories:
            memories.append(clean)
        if len(memories) >= max_memories:
            break

    trace = _clean_text(raw.get("trace"), max_trace_characters) or None
    corrections: list[str] = []
    link_index: int | None = None

    if action == "follow_link":
        candidate = raw.get("link_index")
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            return safe_failure("follow_link did not provide an integer link_index")
        if not can_follow or candidate < 0 or candidate >= link_count:
            return safe_failure("follow_link selected a link outside the bounded candidates")
        link_index = candidate
        if trace:
            trace = None
            corrections.append("ignored trace on follow_link")
    elif action == "carry_trace":
        if not trace:
            action = "leave_silently"
            corrections.append("empty Trace became silence")
    else:
        if trace:
            trace = None
            corrections.append("ignored trace on leave_silently")

    return BrainDecision(
        action=action,
        link_index=link_index,
        observation=observation,
        memories=memories,
        trace=trace,
        status="corrected" if corrections else "accepted",
        error="; ".join(corrections) or None,
    )


class CommandBrain:
    protocol = "stray-brain-v1"

    def __init__(self, command: list[str], *, label: str, timeout_seconds: float = 45.0):
        if not command:
            raise ValueError("brain command must not be empty")
        self.command = command
        self.label = label
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_string(
        cls, command: str, *, label: str, timeout_seconds: float = 45.0
    ) -> "CommandBrain":
        return cls(shlex.split(command), label=label, timeout_seconds=timeout_seconds)

    def decide(
        self,
        payload: dict[str, Any],
        *,
        link_count: int,
        can_follow: bool,
        max_memories: int,
        max_trace_characters: int,
    ) -> BrainDecision:
        request = {"protocol": self.protocol, **payload}
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return safe_failure("brain adapter timed out")
        except OSError as exc:
            return safe_failure(f"brain adapter could not start: {exc.__class__.__name__}")

        if completed.returncode != 0:
            return safe_failure(f"brain adapter exited with code {completed.returncode}")
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return safe_failure("brain adapter returned invalid JSON")

        return normalize_decision(
            raw,
            link_count=link_count,
            can_follow=can_follow,
            max_memories=max_memories,
            max_trace_characters=max_trace_characters,
        )
