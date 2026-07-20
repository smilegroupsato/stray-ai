# Devbox LLM Observation — 2026-07-20

## Environment

- runtime: Ollama bound to `127.0.0.1:11434`
- model: `qwen3.5:9b`
- venue snapshot: `ae3bdba670c87b0057bb85730e8f928fd95cee4b`
- brain protocol: `stray-brain-v1`

## First bounded LLM attempt

The host carried `stray-001` through the trusted reception path:

```text
README.md
→ REPOSITORY_CONTEXT.md
→ AGENTS.md
```

The brain was invoked only at `AGENTS.md`.

The attempt lasted exactly 45 seconds and then produced:

```text
brain adapter timed out
```

The host rejected the unavailable observation, persisted the visit, added no memory, created no Trace, and exited with:

```text
brain_failed_safe_exit
```

No remote write occurred.

## Diagnosis

Two separate timeouts existed:

- HTTP adapter timeout configured for the model request
- outer subprocess timeout, previously defaulting to 45 seconds

The outer timeout ended the adapter before the model request could complete. A direct model probe also consumed its token budget in reasoning and returned empty content.

## Correction

The LLM launcher now defaults to:

- `STRAY_LLM_REASONING_EFFORT=none`
- `STRAY_LLM_JSON_MODE=1`
- `STRAY_LLM_HTTP_TIMEOUT=150`
- `STRAY_BRAIN_TIMEOUT=180`
- `STRAY_LLM_MAX_TOKENS=400`

The deterministic host remains responsible for validating the final response and failing closed.