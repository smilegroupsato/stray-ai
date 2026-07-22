# Wake Decision

A persistent visitor should not revisit merely because a scheduler fired. Waking is a separate bounded judgment, and remaining asleep is a valid result.

## Scope

The wake layer answers only:

```text
remain asleep
or
request a later bounded visit
```

A `request_visit` result does not start a visit. The visitor remains `resting` until a separate visit process begins.

## Trusted body gate

Before any model can be invoked, the host evaluates trusted local state:

- lifecycle status
- elapsed rest time
- time-recovered fatigue
- conservative thresholds from the visitor profile
- opaque previous and candidate snapshot identities
- whether those identities differ
- bounded unresolved impulses

The default `stray-001` policy is:

```yaml
wake:
  minimum_rest_hours: 12
  maximum_fatigue_to_consider: 0.5
  max_new_impulses_per_check: 1
```

If the visitor is not resting, has not rested long enough, or remains too fatigued, the command records `remain_asleep` and does not invoke the model.

## Venue boundary

Wake judgment does not read venue page content.

The wake layer may know only:

```text
candidate Venue identity
previous snapshot identity for that same Venue
candidate snapshot identity
whether a same-Venue comparison is available
whether those snapshot identities differ
```

A changed identity is a reason that may matter, not proof about what changed.

The candidate Venue identity is trusted host input. When it is supplied, the wake layer searches historical Visit records only for the latest snapshot of that same Venue. A Visit to another Venue is never used as the previous snapshot.

An explicitly supplied `--previous-snapshot-id` remains supported and is recorded with comparison scope `explicit_previous`.

When neither a candidate Venue identity nor an explicit previous snapshot is supplied, comparison is recorded as unavailable:

```json
{
  "comparison_available": false,
  "comparison_scope": "unavailable_no_venue",
  "changed": false
}
```

This fail-closed behavior prevents an alternating sequence of Venue visits from producing a false `changed: true` result.

## Bounded wake brain

When the deterministic body gate is eligible, an optional subprocess brain may return:

```json
{
  "decision": "remain_asleep | request_visit",
  "observation": "short account",
  "reason": "short reason",
  "impulses": ["zero or one short impulse"]
}
```

Invalid JSON, invalid decisions, timeout, or adapter failure becomes a rejected decision and fails closed to `remain_asleep`.

The included OpenAI-compatible adapter is:

```text
scripts/openai_compatible_wake_brain.py
```

It has no tools and cannot start the visit process.

## Persistent observation

Every check writes one local record:

```text
agents/<agent-id>/wake_checks/YYYY-MM-DD_HHMMSS.json
```

The record includes eligibility, blockers, rest and fatigue facts, candidate Venue identity, comparison availability and scope, opaque snapshot identities, brain status, final decision, and any safely added impulse.

Wake checks do not increment visit counters and do not modify Visit JSON or Trace files. Existing wake records are historical evidence and are not rewritten after later comparison fixes.

## Approval-only handoff

An accepted `request_visit` may be converted by a separate human-invoked command into one local `pending_human_approval` envelope under `visit_requests/`.

That handoff validates the preserved wake record, a human-supplied existing snapshot root, and a bounded relative route. It does not read venue content, approve the request, or invoke the Visit command.

See [`wake-to-visit-handoff.md`](wake-to-visit-handoff.md).

## CLI

Deterministic safe-default same-Venue check:

```bash
stray-ai-wake \
  --agent /srv/sgos/data/stray-ai/agents/stray-001 \
  --candidate-venue-id eternal-free-party \
  --candidate-snapshot-id SNAPSHOT_ID
```

Optional command brain:

```bash
stray-ai-wake \
  --agent /srv/sgos/data/stray-ai/agents/stray-001 \
  --candidate-venue-id eternal-free-party \
  --candidate-snapshot-id SNAPSHOT_ID \
  --brain command \
  --brain-command "python scripts/openai_compatible_wake_brain.py" \
  --brain-label MODEL_NAME
```

The devbox setup creates launchers that select only an already existing local Eternal Free Party snapshot and pass the trusted Venue ID:

```text
/srv/sgos/data/stray-ai/check-wake-eternal-free-party.sh
/srv/sgos/data/stray-ai/check-wake-eternal-free-party-llm.sh
```

These launchers do not fetch the venue.

## Safety

This layer adds no:

- scheduler
- cron job
- systemd timer
- automatic visit
- remote Trace publication
- remote venue fetch
- venue-content read

A further safety review is still required before a human-approved request may invoke the existing bounded Visit command.
