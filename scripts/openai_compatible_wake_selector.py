#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import urlparse

import httpx

_SYSTEM_PROMPT = """You are a bounded multi-Venue wake selector.
This is not a Visit or a wake command. Venue content is unavailable and must not be inferred.
Do not use tools, execute commands, follow or provide URLs, write anything, or cause automatic actions.
Opaque identity difference is not knowledge of content change. Remaining asleep is valid.
Choose at most one exact candidate Venue ID and return exactly one JSON object with no prose.

Schema:
{
  "decision": "remain_asleep" | "select_venue",
  "selected_venue_id": "exact candidate ID or null",
  "observation": "short bounded account",
  "reason": "short bounded reason",
  "reason_code": "no_specific_reason | rest_preferred | tie_unresolved | opaque_identity_changed | unresolved_impulse | comparison_unavailable"
}

A selection does not wake the visitor, start a Visit, create a Request, or authorize any action.
"""


def _extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response did not contain choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item["text"]
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if parts:
            return "".join(parts)
    raise ValueError("response did not contain text content")


def _parse_json_object(text: str) -> dict[str, Any]:
    value = json.loads(text.strip())
    if not isinstance(value, dict):
        raise ValueError("model output was not a JSON object")
    return value


def main() -> None:
    request = json.load(sys.stdin)
    model = os.environ.get("STRAY_LLM_MODEL")
    if not model:
        raise SystemExit("STRAY_LLM_MODEL is required")
    base_url = os.environ.get("STRAY_LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("STRAY_LLM_BASE_URL must be an http or https URL")
    api_key = os.environ.get("STRAY_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and not api_key:
        raise SystemExit("a remote model endpoint requires STRAY_LLM_API_KEY or OPENAI_API_KEY")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False, indent=2)},
        ],
        "temperature": float(os.environ.get("STRAY_LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("STRAY_LLM_MAX_TOKENS", "300")),
        "reasoning_effort": os.environ.get("STRAY_LLM_REASONING_EFFORT", "none"),
        "stream": False,
    }
    if os.environ.get("STRAY_LLM_JSON_MODE", "0") == "1":
        body["response_format"] = {"type": "json_object"}
    timeout = float(os.environ.get("STRAY_LLM_HTTP_TIMEOUT", "120"))
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    print(json.dumps(_parse_json_object(_extract_content(payload)), ensure_ascii=False))


if __name__ == "__main__":
    main()
