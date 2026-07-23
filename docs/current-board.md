# Stray AI Current Board v0

## Purpose

`Current Board` is a temporary read-only current-state interface used before SGOS Console exists.

It answers three different questions without mixing them into one checklist:

- What is the one current focus?
- What is live right now for `stray-001`?
- What is next, held, recently completed, parked, or explicitly not being done?

It is not a dashboard, scheduler, approval surface, or replacement for the historical Roadmap.

## Sources

The SGOS common specification is:

```text
/srv/sgos/repos/sgos-pkm-core/docs/current-state-interface-pattern.md
```

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

`NOW` requires a title, standalone purpose, stage, next action, and explicit implementation-authorization boolean. Board sections continue to accept strings and simple mappings; a mapping may also define validated `children` with a title and one-line detail for a subordinate group hierarchy.

### Live source

The publisher reads only bounded local operational metadata from one agent directory:

- `state.json`
- the latest valid `wake_checks/*.json`
- `visit_requests/*.json` status values
- the persistent Visit counter

It does not read Venue page content, memory text, Visit page contents, Trace text, snapshot files, raw brain commands, or approval plans.

Local paths found in source data are not rendered.

## Publication

The manual publisher writes exactly one file beneath the existing shared runtime root:

```text
/srv/sgos/data/current-board/stray-ai/index.html
```

Its canonical Internal Service Gateway URL is:

```text
/current-board/stray-ai/
```

The shared Current Board Index is `/current-board/`. The retained Stray AI
namespace and Visit Report entrance is `/stray-ai/`.

The devbox helper is:

```text
scripts/devbox/publish-stray-ai-current-board-v0.sh
```

The publisher performs an atomic replacement. A source-validation or safety failure preserves the previous HTML.

The legacy `/stray-ai/current/` surface remains unchanged until the new surface
passes LAN and Tailscale HTTP and hash verification. After that verification,
the redirect is owned by Internal Server Build; this implementation neither
creates nor claims completion of that redirect.

## Separation from Visit Report

Current Board is an operational current-state view. Visit Report remains an observation archive.

Current Board LIVE contains one read-only relative link to the retained Visit Report entrance and a restrained link to the shared Current Board Index. No reverse Current Board link is added to Visit Reports, maps, world views, or source archive navigation.

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
