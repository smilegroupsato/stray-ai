# Internal Gateway Request Review v0

## Purpose

This milestone makes the existing read-only Visit Request review visible through the already deployed Internal Service Gateway.

It does not turn the review page into an operational control surface. It only publishes a static HTML snapshot after a human explicitly invokes the publisher.

## URL and source

The Gateway already serves the rendered Stray AI report root:

```text
/srv/sgos/data/stray-ai/reports
        ↓
/stray-ai/
```

The Request review is published at:

```text
/srv/sgos/data/stray-ai/reports/request-review/index.html
        ↓
http://192.168.1.20/stray-ai/request-review/index.html
http://100.79.124.53/stray-ai/request-review/index.html
```

No Caddy route, listener, firewall rule, DNS record, HTTPS setting, or service unit is changed by this milestone.

## Observation boundary

Visit Reports remain an observation window for past encounters.

The Request review is an operational read model for pending, approved, cancelled, malformed, or completed Request envelopes. It is not linked from Visit Report pages, collection pages, maps, or the observed world.

This separation prevents current approval state from being mistaken for part of the visitor's observed world.

## Explicit publishing

Generic command:

```bash
stray-ai-publish-request-review \
  --agent /local/agent \
  --report-root /local/rendered-report-root
```

Devbox helper:

```bash
bash scripts/devbox/publish-stray-ai-request-review-v0.sh
```

The helper is intentionally manual and requires the host short name to be `devbox`.

## Published material

The publisher builds the review collection in memory and publishes exactly:

```text
request-review/index.html
```

It does not publish:

- JSON or JSONL summaries;
- raw Request envelopes;
- wake records;
- snapshot roots;
- outbox coordinates;
- full brain commands;
- memory records;
- Visit JSON;
- claims;
- Trace files;
- repository source.

The command result printed to the terminal includes only the local output coordinate, Gateway path, Request count, status counts, and safety boundaries.

## Static safety checks

Before replacement, the publisher verifies that the rendered HTML:

- retains the read-only notice;
- contains no form or button;
- contains no JavaScript action surface;
- contains no `file://` coordinate;
- contains no `/srv/...` coordinate;
- contains no `snapshot_root` field;
- contains no `brain_command` field.

It also rejects:

- a missing report root;
- a symlinked `request-review` directory;
- a symlinked `index.html`;
- any JSON-like file already placed in the public Request review directory.

## Atomic replacement

The full collection and HTML are prepared before the destination is selected for replacement.

The final HTML is written to a temporary sibling file, flushed, and atomically replaced. A validation or rendering failure before replacement leaves the previously published page unchanged.

## What publishing does not do

Publishing does not invoke:

- wake judgment;
- snapshot creation or fetch;
- handoff preparation;
- approval;
- cancellation;
- execution claim;
- Visit execution;
- Visit Report regeneration;
- Caddy reload;
- scheduler, cron, timer, poller, or queue worker;
- remote write or Trace publication.

A newly created or changed Request is not automatically reflected. A human must explicitly publish another static snapshot.

## Empty state

When an individual has no top-level Visit Requests, the published page is still valid and states that no Request exists.

This is a successful and meaningful state. It does not create a placeholder Request or imply that a wake check should occur.

## Validation boundary

Implementation validation uses synthetic agents and report roots first. A real devbox publish for `stray-001` is a separate explicit operation after tests and CI pass.

The real publish may change only the rendered file under:

```text
/srv/sgos/data/stray-ai/reports/request-review/index.html
```

Persistent `stray-001` records must remain byte-identical.
