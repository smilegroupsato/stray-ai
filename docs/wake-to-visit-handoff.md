# Wake-to-Visit Handoff v0

Wake judgment and Visit execution remain separate operations.

This layer turns one accepted local `request_visit` wake record into a local approval envelope. It does not approve or start a Visit.

## Boundary

The handoff command may:

- read one preserved wake-check JSON under the selected agent
- read the agent profile for the Visit place limit
- receive a trusted venue target from the human operator
- validate path containment and opaque snapshot identity
- write one local pending request

It may not:

- fetch or refresh a venue snapshot
- read venue page contents
- invoke a wake brain
- invoke `run_visit`
- change agent state or unresolved impulses
- alter wake records, Visit JSON, memory, Trace, or reports
- approve its own request
- schedule or automatically execute anything

## Input

A request can be prepared only from a wake record that says all of the following:

- `eligible` is true
- `decision` is `request_visit`
- the wake brain status is `accepted` or `corrected`
- the visitor remained `resting`
- `current_location_after` is null
- the candidate snapshot identity is present

The human operator separately supplies:

- venue id
- an already existing local snapshot root
- entrance path relative to that root
- an optional trusted arrival path relative to that root

The snapshot directory name must exactly match the opaque candidate snapshot identity in the wake record. This is an identity check, not a content comparison.

## Output

The command writes:

```text
agents/<agent-id>/visit_requests/<request-id>.json
```

The envelope uses schema:

```text
stray-visit-request-v1
```

Its status is always:

```text
pending_human_approval
```

It records:

- source wake record and SHA-256
- wake observation, reason, and added impulse
- trusted venue id and snapshot identity
- bounded relative entrance and arrival path
- explicit non-execution constraints
- empty approval and execution fields

Preparing the same wake record and target again returns the existing envelope without duplication. A conflicting target fails closed.

## CLI

```bash
stray-ai-prepare-visit \
  --agent /srv/sgos/data/stray-ai/agents/stray-001 \
  --wake-record /srv/sgos/data/stray-ai/agents/stray-001/wake_checks/RECORD.json \
  --venue-id eternal-free-party \
  --snapshot-root /srv/sgos/data/stray-ai/venues/eternal-free-party/SNAPSHOT_ID \
  --entrance README.md \
  --arrival-path REPOSITORY_CONTEXT.md AGENTS.md
```

This command does not read those venue pages and does not start the Visit.

## Future review

A later, separate safety review may define how a human explicitly approves one pending envelope and how an approved envelope may be passed to the existing bounded Visit command.

That future layer must still exclude schedulers, automatic approval, automatic venue fetch, and automatic remote Trace publication.
