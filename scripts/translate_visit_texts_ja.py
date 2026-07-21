#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from stray_ai.report_translations import source_digest

_AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_SYSTEM_PROMPT = """Translate the supplied source text into natural Japanese.
Preserve timestamps, filenames, identifiers, quoted words, and factual meaning.
Do not add interpretation, explanation, or new facts.
Return exactly one JSON object: {"translation": "..."}
"""


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _extract_texts(visits_dir: Path) -> list[str]:
    texts: list[str] = []
    for path in sorted(visits_dir.glob("*.json")):
        visit = _load_json(path)
        if visit is None:
            continue
        steps = visit.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                brain = step.get("brain")
                if not isinstance(brain, dict):
                    continue
                observation = brain.get("observation")
                if isinstance(observation, str) and observation.strip():
                    texts.append(observation.strip())
        memories = visit.get("memories_added")
        if isinstance(memories, list):
            for memory in memories:
                if isinstance(memory, str) and memory.strip():
                    texts.append(memory.strip())
    return list(dict.fromkeys(texts))


def _load_existing(path: Path) -> dict[str, str]:
    value = _load_json(path)
    if value is None or value.get("version") != 1:
        return {}
    entries = value.get("translations")
    if not isinstance(entries, list):
        return {}
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        translation = entry.get("translation")
        digest = entry.get("source_sha256")
        if not isinstance(source, str) or not isinstance(translation, str):
            continue
        if digest != source_digest(source):
            continue
        if source.strip() and translation.strip():
            result[source] = translation.strip()
    return result


def _extract_translation(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("translation response did not contain choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("translation response did not contain a message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("translation response did not contain text")
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict) or not isinstance(value.get("translation"), str):
        raise ValueError("translation response did not match the schema")
    translation = value["translation"].strip()
    if not translation:
        raise ValueError("translation response was empty")
    return translation


def _translate(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
    api_key: str | None,
    source: str,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": source},
        ],
        "temperature": 0,
        "max_tokens": int(os.environ.get("STRAY_TRANSLATION_MAX_TOKENS", "500")),
        "reasoning_effort": os.environ.get("STRAY_LLM_REASONING_EFFORT", "none"),
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    response = client.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=body,
    )
    response.raise_for_status()
    return _extract_translation(response.json())


def _write_cache(
    path: Path,
    *,
    model: str,
    translations: dict[str, str],
) -> None:
    entries = [
        {
            "source_sha256": source_digest(source),
            "source": source,
            "translation": translations[source],
        }
        for source in sorted(translations)
    ]
    value = {
        "version": 1,
        "language": "ja",
        "model": model,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "translations": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o640)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Japanese display translations without changing Visit JSON."
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=Path("/srv/sgos/data/stray-ai/agents"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/srv/sgos/data/stray-ai/report-translations"),
    )
    parser.add_argument("--agent-id")
    args = parser.parse_args()

    model = os.environ.get("STRAY_LLM_MODEL")
    if not model:
        raise SystemExit("STRAY_LLM_MODEL is required")
    base_url = os.environ.get(
        "STRAY_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
    ).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("STRAY_LLM_BASE_URL must be an http or https URL")
    api_key = os.environ.get("STRAY_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and not api_key:
        raise SystemExit("a remote model endpoint requires an API key")

    if args.agent_id:
        if _AGENT_ID.fullmatch(args.agent_id) is None:
            raise SystemExit("invalid agent id")
        agent_dirs = [args.agents_dir / args.agent_id]
    else:
        agent_dirs = [
            path
            for path in sorted(args.agents_dir.iterdir())
            if path.is_dir() and _AGENT_ID.fullmatch(path.name)
        ]

    timeout = float(os.environ.get("STRAY_LLM_HTTP_TIMEOUT", "150"))
    summary: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for agent_dir in agent_dirs:
            visits_dir = agent_dir / "visits"
            if not visits_dir.is_dir():
                continue
            output = args.output_dir / f"{agent_dir.name}.ja.json"
            translations = _load_existing(output)
            sources = _extract_texts(visits_dir)
            translated_now = 0
            for source in sources:
                if source in translations or _JAPANESE.search(source):
                    continue
                translations[source] = _translate(
                    client,
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    source=source,
                )
                translated_now += 1
            _write_cache(output, model=model, translations=translations)
            summary.append(
                {
                    "agent_id": agent_dir.name,
                    "source_text_count": len(sources),
                    "translated_now": translated_now,
                    "cached_translation_count": len(translations),
                    "output_file": str(output),
                }
            )

    print(json.dumps({"agents": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
