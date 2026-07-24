# Visit Report Multiple Individuals

Visit Report v0 Phase 4 turns the report output into a read-only collection of persistent individuals.

It does not create a second individual. It only discovers already existing agent directories under an explicit `agents` root and generates isolated reports for each one.

## Output structure

```text
reports/
├─ index.html                         collection entrance
├─ visits.html                        primary archive compatibility
├─ latest.html                        primary latest compatibility
├─ map.html                           primary map compatibility
├─ <primary visit>.html               primary named-report compatibility
└─ individuals/
   └─ <agent-id>/
      ├─ index.html
      ├─ latest.html
      ├─ map.html
      └─ <visit>.html
```

The root collection entrance shows bounded metadata only:

- agent id
- optional display name
- current status
- preserved Visit count
- last Visit time
- relative links to that individual's archive, latest Report, and observed map

An already born individual remains visible when its preserved Visit count is
zero. Its card is marked `NO VISITS YET`, links to its empty archive and
observed map, and does not expose a nonexistent latest Report. This lets a new
individual such as `stray-002` appear truthfully without creating or simulating
a Visit.

Memory content, absolute local paths, secrets, and raw venue content are not rendered in the collection entrance.

## Isolation

Each individual receives a separate output namespace. Existing Phase 1–3 generation runs independently inside that namespace.

This prevents:

- Visit routes from different individuals being merged
- one individual's state appearing on another individual's Report
- observed maps combining individuals without an explicit world-map layer
- named Report filenames colliding between individuals

Phase 4 is not the Stray AI world map. A future layer may deliberately combine individual experience while preserving attribution.

## Primary compatibility

The generator accepts an explicit primary individual.

The primary individual's generated files are copied to the historical root routes so the Internal Service Gateway can continue serving:

```text
/stray-ai/latest.html
/stray-ai/map.html
/stray-ai/<named-visit>.html
```

The primary Visit archive is also copied to `visits.html`. Root `index.html` becomes the all-individual collection entrance.

No Caddy or Gateway configuration change is required.

## Discovery rules

Only immediate child directories with safe identifiers are accepted. The identifier must:

- start with an ASCII letter or digit
- contain only letters, digits, `.`, `_`, and `-`
- remain at most 64 characters

Unsafe directory names are skipped and reported. An explicitly requested primary individual must exist before any generated subtree is replaced.

## Regeneration

Collection generation refreshes the generated `individuals/` subtree and removes stale root compatibility Report files. It does not modify:

- profile
- memory
- state
- Visit JSON
- wake-check records
- Trace files

## CLI

```bash
stray-ai-report \
  --agents-dir /srv/sgos/data/stray-ai/agents \
  --primary-agent stray-001 \
  --output-dir /srv/sgos/data/stray-ai/reports
```

The existing `--visit` and `--visits-dir` modes remain available for single-individual generation and tests.

## Boundaries

Phase 4 adds no automatic birth, wake decision, Visit, scheduler, remote fetch, or remote write. It is a static observation surface only.

Generating or publishing the persistent devbox Report remains a separate,
explicit manual operation. Repository implementation and tests do not modify
persistent agent data or the served Report tree.
