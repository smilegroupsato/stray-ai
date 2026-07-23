# Stray AI Current Board v0

## Purpose

`Current Board` is a temporary read-only current-state interface used before SGOS Console exists.

It answers three different questions without mixing them into one checklist:

- What is the one current focus?
- What is live right now for `stray-001`?
- What is next, held, recently completed, parked, or explicitly not being done?

It is not a dashboard, scheduler, approval surface, or replacement for the historical Roadmap.

## Sources

### Plan source

```text
registry/current_board.yml
```

This file is the source of truth for:

- `NOW` — exactly one current focus
- `NEXT`
- `HOLD / WAIT`
- `RECENTLY DONE`
- `PARKING LOT`
- `NOT DOING`

`NOW` requires a title, stage, next action, and explicit implementation-authorization boolean.

### Live source

The publisher reads only bounded local operational metadata from one agent directory:

- `state.json`
- the latest valid `wake_checks/*.json`
- `visit_requests/*.json` status values
- the persistent Visit counter

It does not read Venue page content, memory text, Visit page contents, Trace text, snapshot files, raw brain commands, or approval plans.

Local paths found in source data are not rendered.

## Publication

The manual publisher writes exactly one file:

```text
reports/current/index.html
```

On the existing Internal Service Gateway it is available at:

```text
/stray-ai/current/index.html
```

The devbox helper is:

```text
scripts/devbox/publish-stray-ai-current-board-v0.sh
```

The publisher performs an atomic replacement. A source-validation or safety failure preserves the previous HTML.

## Separation from Visit Report

Current Board is an operational current-state view. Visit Report remains an observation archive.

No Current Board link is added to Visit Reports, maps, world views, or source archive navigation in v0.

## Safety boundary

Current Board v0 adds no:

- form, button, JavaScript, or action control
- JSON or JSONL publication
- local absolute path exposure
- snapshot fetch
- Venue-content read
- wake check
- Visit Request creation, approval, cancellation, claim, or execution
- Visit or report regeneration
- scheduler, cron, systemd timer, or automatic publish
- SGOS Console implementation

The YAML may later become an input to a Console card, but Console remains a separate future design decision.
