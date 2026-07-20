# Coherent Return — Devbox Observation — 2026-07-20

## Scope

The persistent `stray-001` habitat on devbox was migrated without starting another visit or invoking the language model.

A complete backup of the agent directory was created before migration.

## Environment

- host: devbox
- repository branch: `agent/coherent-return-state`
- local Python: 3.14.4
- local test result: 17 passed
- GitHub Actions: Python 3.11 and 3.12 passed

## Preserved history

Before and after migration:

```text
Visit JSON files: 4 -> 4
Trace files:      1 -> 1
```

SHA-256 comparison confirmed that all four existing Visit JSON files remained unchanged.

The dated memory entries were preserved. Only the exact obsolete bootstrap statement was replaced with timeless memory preamble text.

## Migrated state

```text
status:                       resting
current_location:             null
visit_count:                  4
llm_visit_count:              2
accepted_brain_visit_count:   1
safe_exit_count:              1
last_exit_reason:             left_silently
last_backend:                 command
last_model:                   qwen3.5:9b
```

`last_location` retains the final historical `AGENTS.md` page from the immutable Eternal Free Party snapshot. It is no longer represented as the visitor's current presence.

## Idempotence

The migration was run a second time and returned:

```json
{
  "memory_changed": false,
  "state_changed": false
}
```

## Safety result

- no new visit was started
- no LLM request was made
- no Trace was created or removed
- no Visit JSON was modified
- no remote write occurred

The coherent-return devbox gate passed. `stray-001` is now represented as home and resting after its first accepted bounded LLM visit.
